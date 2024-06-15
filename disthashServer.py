import grpc
import disthash_pb2_grpc
import WALog
import ROSLog
import threading
import time
import random
import logging
import argparse

from concurrent import futures
from enum import Enum
from google.protobuf.empty_pb2 import Empty
from disthash_pb2 import GetResponse, RequestVoteArgs, \
                         RequestVoteResponse, AppendEntriesArgs, \
                         AppendEntriesResponse, LogEntry

# Configure the root logger
logging.basicConfig(level=logging.DEBUG,  # Set the root logger level to DEBUG
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')

logger = logging.getLogger(__name__)

class DistHashServicer(disthash_pb2_grpc.DistHashServicer):


    class Mode(Enum):
        LEADER = 1
        CANDIDATE = 2
        FOLLOWER = 3

    def __init__(self, id, ports):
        self.data = {}
        self.dataLock = threading.Lock()
        self.stateLock = threading.Lock()
        # ideally we should take state lock before doing 
        # remaining operations below

        self.id = id       # this node is running on ports[id]
        self.ports = ports # ports of all DistHash nodes
        self.clients = {}  # a grpc client for talking to other nodes
        self._create_clients()
        self.leaderId = -1 # no known leader yet
        self.rpcTimeout = 5 # seconds
        self.log = WALog.WALog(f"log.{self.id}")
        self._replay_log() # restore previous log entries if any
        self.ROS = ROSLog.ROSLog(f"ROSlog.{self.id}")
        self.mode = self.Mode.FOLLOWER
        self.commitIndex = 0 # index of highest log entry known to be
                             # committed (initialized to 0, increases
                             # monotonically)
        self.lastApplied = 0 # index of highest log entry applied to state
                             # machine (initialized to 0, increases
                             # monotonically)
        
        # only for leaders, to be reinitialized after election
        # should these dicts be lock protected as well?
        self.nextIndex = {} # for each server, index of the next log entry
                            # to send to that server (initialized to leader
                            # last log index + 1)

        self.matchIndex = {} # for each server, index of highest log entry
                             # known to be replicated on server
                             # (initialized to 0, increases monotonically)

        self.heartBeatTimeout = 2 + 2*random.random() # seconds

        # for follower
        self.lastAppendEntriestime = 0 # last instant in time when this node received
                                       # an appendEntries request from a leader

        # only for candiddates
        self.votesToLead = int(len(self.ports)/2) + 1
        self.majority = self.votesToLead
        self.receivedVotes = 0 
        self.reElectionTimeout = 2 + 2*(random.random()) # seconds (time after which a new election is started
                                                           # if nobody won)
        
        # State machine from Fig 4 in https://raft.github.io/raft.pdf
        state_machine = threading.Thread(target=self.follow) # start as a follower
        state_machine.daemon = True # do not wait for this thread to exit
        state_machine.start()

    def _replay_log(self):
        """
        To restore previous in-memory state
        """
        lastidx = self.log.getLastIndex()
        for i in range(lastidx):
            # log is 1-indexed
            indexToBeApplied = i+1
            le = self.log.readEntry(indexToBeApplied)
            self._set(le.request.key, le.request.value)
            logging.info(f"Node {self.id}: Restoring the entry: ({le.request.key}, {le.request.value})")


    def _create_clients(self):
        for i, port in enumerate(self.ports):
            if i != self.id:
                channel = grpc.insecure_channel(f'localhost:{port}')
                self.clients[i] = disthash_pb2_grpc.DistHashStub(channel)         

    def reinit_leader(self):
        """
        Re-initialized {self.nextIndex} and {self.matchIndex}
        """
        lastIndex = self.log.getLastIndex()
        for i, port in enumerate(self.ports):
            self._set_nextIndex(i, lastIndex+1)
            self._set_matchIndex(i, 0)

    def _get_lastAppendEntriestime(self):
        with self.stateLock:
            return self.lastAppendEntriestime
    
    def _set_lastAppendEntriestime(self):
        with self.stateLock:
            self.lastAppendEntriestime = time.time()

    def _get_mode(self):
        with self.stateLock:
            return self.mode
        
    def _set_mode(self, mode):
        with self.stateLock:
            self.mode = mode

    def _get_leaderId(self):
        with self.stateLock:
            return self.leaderId
        
    def _set_leaderId(self, id):
        with self.stateLock:
            self.leaderId = id
    
    def _set_nextIndex(self, key, value):
        with self.stateLock:
            self.nextIndex[key] = value

    def _get_nextIndex(self, key):
        with self.stateLock:
            return self.nextIndex[key]
        
    def _set_matchIndex(self, key, value):
        with self.stateLock:
            self.matchIndex[key] = value

    def _get_matchIndex(self, key):
        with self.stateLock:
            return self.matchIndex[key]

    
    def _trasition_to_candidate(self):
        with self.stateLock:
            # follower ---> candidate
            assert self.mode != self.Mode.LEADER, "Leaders are not allowed to become candidates!"
            self.mode = self.Mode.CANDIDATE
            # increment current term
            self.ROS.setCurrTerm(self.ROS.getCurrTerm() + 1)
            # vote for itself
            self.ROS.setVotedFor(self.id)
            self.receivedVotes = 1

    def _incr_receivedVotes(self):
        with self.stateLock:
            self.receivedVotes += 1

    def _get_receivedVotes(self):
        with self.stateLock:
            return self.receivedVotes
        
    def _get_commitIndex(self):
        with self.stateLock:
            return self.commitIndex
    
    def _set_commitIndex(self, idx):
        with self.stateLock:
            self.commitIndex = idx

    def _get_lastApplied(self):
        with self.stateLock:
            return self.lastApplied
        
    def _set_lastApplied(self, idx):
        with self.stateLock:
            self.lastApplied = idx

    def follow(self):
        '''
        Checks for periodic heartbeats
        '''
        assert self.mode == self.Mode.FOLLOWER, "Mode should be set to follower, before calling follow()"
        logger.info(f"Node {self.id}: now a follower")
        while True:
            time.sleep(self.heartBeatTimeout)
            lastheartbeat = self._get_lastAppendEntriestime()
            if (time.time() - lastheartbeat) > self.heartBeatTimeout:
                # no heartBeat received in last {self.heartBeatTimeout} seconds!
                logging.info(f"Node {self.id}: heartbeat timeout! received last heartbeat at {lastheartbeat} epoch, starting an election.")
                self.contest_election()

    def _trasition_to_leader(self):
        with self.stateLock:
            # candidate ----> leader
            assert self.mode == self.Mode.CANDIDATE, "Only candidates are allowed to become leaders!"
            self.mode = self.Mode.LEADER
        self.reinit_leader()

    def _transition_to_follower(self, newTerm):
        with self.stateLock:
            self.mode = self.Mode.FOLLOWER
            self.ROS.setCurrTerm(newTerm)
            self.ROS.setVotedFor(-1)

    def _prepare_aeargs(self, i):
        #logger.debug(f"Node {self.id}: preparing args for node {i}")
        aeargs = AppendEntriesArgs()
        aeargs.leaderterm = self.ROS.getCurrTerm()
        aeargs.leaderId = self.id
        aeargs.prevLogIndex = 0
        aeargs.prevLogTerm  = 0
        aeargs.leaderCommitIndex = self._get_commitIndex()

        if (self.log.getLastIndex() >= self._get_nextIndex(i)):
            idx = self._get_nextIndex(i)
            logger.debug(f"Node {self.id}: nextIndex for node {i} is {idx}")
            aeargs.prevLogIndex = idx - 1 # index of log entry immediately preceding new ones
            if (aeargs.prevLogIndex > 0):
                aeargs.prevLogTerm = self.log.readEntry(aeargs.prevLogIndex).term
            while (idx <= aeargs.prevLogIndex):
                logger.debug(f"Node {self.id}: appending entry at idx {idx}")
                aeargs.entries.append(self.log.readEntry(idx))
                idx += 1
        return aeargs


    def lead(self):
        '''
        Lead!
        '''
        self._trasition_to_leader()
        logger.info(f"Node {self.id}: now a leader, starting periodic heartbeats")
        # send periodic heart beats
        while True:

            # Ensure we are still the leader 
            if (self._get_mode() != self.Mode.LEADER):
                assert self._get_mode() == self.Mode.FOLLOWER, "A leader can only transition to a follower!"
                self.follow()

            # send heartbeats to all other nodes
            for i, _ in enumerate(self.ports):
                if i != self.id:
                    aeargs = self._prepare_aeargs(i)
                    t = threading.Thread(target=self._send_heartbeat, args=(aeargs, i))
                    t.daemon = True
                    t.start()

            # I don't think leader needs to wait for above threads to finish
            # before sending heartbeats again

            time.sleep(0.2) # every so often TODO: Remove magic number (must be less than heartbeat timeout)
            


    def _send_heartbeat(self, aeargs: AppendEntriesArgs, i):
        try:
            if (self._get_mode() != self.Mode.LEADER):
                # (need the check twice in case this is a retry)
                return

            res = self.clients[i].AppendEntries(aeargs, timeout = self.rpcTimeout)

            if (self._get_mode() != self.Mode.LEADER):
                return
            
            if res.success:
                self._set_nextIndex(i, aeargs.prevLogIndex + 1)
                self._set_matchIndex(i, max(self._get_matchIndex(i), aeargs.prevLogIndex))
            else:
                # maybe the term needs to be updated
                if (res.term > self.ROS.getCurrTerm()):
                    # we are a stale leader, should go
                    # back to follower state
                    logging.info(f"Node {self.id}: Node {i} replied with a greater term ({res.term}), transitioning to a follower...")
                    self._transition_to_follower(res.term)
                    return
                
                # if reached here, it means that AppendEntries failed because
                # log consistency check failed
                # reduce self.nextIndex[i] and try again
                self._set_nextIndex(i, self._get_nextIndex(i) - 1)
                aeargs = self._prepare_aeargs(i)
                self._send_heartbeat(aeargs, i)

        except grpc.RpcError as e:
            if e.code() in [grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.UNAVAILABLE] :
                # retry
                logging.debug(f"Node {self.id}: Node {i} didn't respond due to following error {e.code()}, retrying...")
                time.sleep(1) # wait for 1 sec and try again
                self._send_heartbeat(aeargs, i)
            else:
                raise e


    def contest_election(self):
        self._trasition_to_candidate()
        logging.info(f"Node {self.id}: now a candidate")
        rvargs = RequestVoteArgs()
        rvargs.term = self.ROS.getCurrTerm()
        rvargs.candidateId = self.id
        rvargs.lastLogIndex = self.log.getLastIndex()
        rvargs.lastLogTerm = self.log.getLastTerm()
        
        logging.debug(f"Node {self.id}: Requesting vote from remaining nodes...")

        # collect votes from all other nodes
        for i, _ in enumerate(self.ports):
            if i != self.id:
                t = threading.Thread(target=self._get_vote, args=(rvargs, i))
                t.daemon = True # these threads will become useless if this
                                # node transitions back to follower
                t.start()
        
        start_time = time.time()
        while True:

            if (self._get_mode() == self.Mode.FOLLOWER):
                # another node established themselves as
                # leader, return to follower state
                logging.debug(f"Node {self.id}: Not a candidate, another node estabilised themselves as leader")
                self.follow() # threads requesting for vote will exit harmlessly because
                              # of checks present in _get_vote()

            if (time.time() - start_time >= self.reElectionTimeout):
                # no leader eleceted in the given time
                # start election again!
                logging.debug(f"Node {self.id}: No leader was elected, starting the election again!")
                self.contest_election() # threads requesting for vote will exit harmlessly because
                                        # of checks present in _get_vote()

            if (self._get_receivedVotes() >= self.votesToLead):
                # we can become the leader!
                logging.debug(f"Node {self.id}: Received majority!")
                self.lead()

            # if none of the above is true, continue
            # to wait


    def _get_vote(self, rvargs, i):
        '''
        requests vote from ith node and updates {self.receivedVotes}
        '''
        try:
            if (self._get_mode() != self.Mode.CANDIDATE):
                # we are not candidate any more!
                # (need the check twice in case this is a retry)
                return
            #logging.debug(f"Node {self.id}: Requesting vote from node {i}")
            res = self.clients[i].RequestVote(rvargs, timeout = self.rpcTimeout)

            if (self._get_mode() != self.Mode.CANDIDATE):
                # we are not candidate any more!
                return
            
            if (self.ROS.getCurrTerm() > rvargs.term):
                # if this node's current term is more 
                # than the rvargs, this means, this node
                # has launched a new election and this is
                # a stale _get_vote() request
                return

            if res.voteGranted:
                self._incr_receivedVotes()
            else:
                # XXX: figure out what to do here
                # I think nothing to do in else
                pass

        except grpc.RpcError as e:
            if e.code() in [grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.UNAVAILABLE] :
                # retry
                #logging.debug(f"Node {self.id}: Node {i} didn't respond due to following error {e.code()}, retrying...")
                time.sleep(0.2) # wait for 1 sec and try again!
                self._get_vote(rvargs, i)
            else:
                raise e # I don't expect any other error, so let's raise this
        #finally:
            #logging.debug(f"Node {self.id}: Received vote from node {i}")
        

        
    def _apply_commited_entries(self):
        '''
        Apply commited entries from the log of this state machine.
        Also updated {self.lastApplied} accordingly
        '''
        while (self._get_commitIndex() > self._get_lastApplied()):
            # apply log[lastApplied + 1] to this node
            indexToBeApplied = self._get_lastApplied() + 1
            le = self.log.readEntry(indexToBeApplied)
            self._set(le.request.key, le.request.value)
            logging.info(f"Node {self.id}: Applied a new entry: ({le.request.key}, {le.request.value})")
            self._set_lastApplied(indexToBeApplied)

    def _set(self, key, value):
        '''
        Actually do the set operation
        '''
        with self.dataLock:
            self.data[key] = value

    def Set(self, request, context):
        import pdb
        pdb.set_trace()
        
        while self._get_mode() != self.Mode.LEADER:
            if self._get_mode() == self.Mode.FOLLOWER:
                # forward this request to whoever is
                # the last known leader
                # (I think this can fail if the last know leader is dead
                #  or no leader is known untill this point)
                return self.clients[self._get_leaderId()].Set(request, context)
            else:
                # I am a candidate, wait to become leader or follower
                pass
        
        currIndex = self.log.appendEntry(LogEntry(request=request, term=self.ROS.getCurrTerm()))
        
        replicatedOn = 1 # at least replicated on me
        replicatedNodes = set([self.id])
        while True:
            # wait until currIndex is replicated on
            # majority of nodes
            for id, _ in enumerate(self.ports):
                if (id not in replicatedNodes):
                    if self._get_matchIndex(id) >= currIndex:
                        # replicated on {id}th node
                        replicatedOn += 1
                        replicatedNodes.add(id)
            
            if (replicatedOn >= self.majority):
                break
        
        # mark this request committed 
        # (this marks all the requests before it as committed as well)
        self._set_commitIndex(max(currIndex, self._get_commitIndex()))
        self._apply_commited_entries()

        return Empty()
    
    def Get(self, request, context):
        import pdb
        pdb.set_trace()
        # Not forwarding to the leader, eventual consistency.
        with self.dataLock:
            if self.data.get(request.key) is None:
                return GetResponse(value="", notFound=True)
            return GetResponse(value = self.data.get(request.key))
        
    def RequestVote(self, request : RequestVoteArgs, context):
        res = RequestVoteResponse()
        res.term = self.ROS.getCurrTerm()
        if request.term < self.ROS.getCurrTerm():
            # requesting candidate is on an older
            # term, reject.
            logger.info(f"Node {self.id}: Rejecting candidate {request.candidateId} with older term ({request.term})")
            res.voteGranted = False
            return res
        
        if self.ROS.getVotedFor() in [-1, request.candidateId]:
            # grant vote if candidate’s log is at
            # least as up-to-date as receiver’s log
            # XXX: Maybe this condition needs to be improved
            if (request.lastLogTerm >= self.log.getLastTerm() and
                request.lastLogIndex >= self.log.getLastIndex()):
                logger.info(f"Node {self.id}: Voting for candidate {request.candidateId}")
                res.voteGranted = True
                self.ROS.setVotedFor(request.candidateId)
                return res
        
        logger.info(f"Node {self.id}: Rejecting candidate {request.candidateId}, as it is not as updated as myself!")
        res.voteGranted = False
        return res 

    def AppendEntries(self, request : AppendEntriesArgs, context):

        # if a candidate/stale leader gets this RPC from a legitimate leader
        # they need to return to follower state
        if (self._get_mode() != self.Mode.FOLLOWER):
            if (request.leaderterm >= self.ROS.getCurrTerm()):
                logger.info(f"Node {self.id}: A legit leader found, returning to being follower...")
                self._set_lastAppendEntriestime()
                # setting the mode to follower would
                # interrupt the election process and make this
                # candidate return to follow()
                self._transition_to_follower(request.leaderterm)
            else:
                # sender is stale leader, ignore this RPC
                res = AppendEntriesResponse()
                res.term = self.ROS.getCurrTerm()
                res.success = False
                return res

        logger.debug(f"Node {self.id}: AppendEntries : {request}")

        self._set_lastAppendEntriestime()
        res = AppendEntriesResponse()
        res.term = self.ROS.getCurrTerm()

        if request.leaderterm < self.ROS.getCurrTerm():
            # leader is on an older term
            logger.debug(f"Node {self.id}: AppendEntries:  Leader is old!")
            res.success = False
            return res

        if (self._get_leaderId() != request.leaderId):
            self._set_leaderId(request.leaderId)

        try:
            if request.prevLogIndex > 0:
                le = self.log.readEntry(request.prevLogIndex)
                if le.term != request.prevLogTerm:
                    # delete all the entries ahead because we
                    # are inconsistent with the leader
                    self.log.deleteAhead(request.prevLogIndex)
                    res.success = False
                    logger.debug(f"Node {self.id}: AppendEntries:  We are inconsistent with the leader")
                    return res
        except WALog.WALog.IndexNotFound:
            # we are way behind the leader
            logger.debug(f"Node {self.id}: AppendEntries:  We are way behind leader")
            res.success = False
            return res
        
        logger.debug(f"Node {self.id}: AppendEntries:  # of entries is {len(request.entries)}")
        idxLast = None
        for entry in request.entries:
            if entry.index <= self.log.getLastIndex():
                # this entry already exists in our log
                # skip
                continue
            logger.debug(f"Node {self.id}: AppendEntries:  appending the entry {entry}")
            idxLast = self.log.appendEntry(entry)

        if request.leaderCommitIndex > self._get_commitIndex():
            newCommitIdx = request.leaderCommitIndex
            if idxLast is not None:
                newCommitIdx = min(newCommitIdx, idxLast)
            self._set_commitIndex(newCommitIdx)

        # Ideally the below step does not need to be part of 
        # AppendEntries() and can be done separately
        self._apply_commited_entries()

        res.success = True
        logger.debug(f"Node {self.id}: AppendEntries:  returning!")
        return res
        

def main():
    parser = argparse.ArgumentParser(description="A script to start a DistHash Server") 
    parser.add_argument("-p", "--ports", required=True, type=int, nargs='+')
    parser.add_argument("-i", "--index", required=True, type = int)
    parser.add_argument("-w", "--workers", required=False, default=10)
    args = parser.parse_args()
    # Create the server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=args.workers))
    disthash_pb2_grpc.add_DistHashServicer_to_server(DistHashServicer(args.index, args.ports), server)
    server.add_insecure_port(f"[::]:{args.ports[args.index]}")
    server.start()
    logging.info(f"DistHash Server now listening at port {args.ports[args.index]}")
    server.wait_for_termination()


if __name__ == '__main__':
    main()




        
            
    

    

