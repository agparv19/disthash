from disthash_pb2 import ROS
import os
import threading

class ROSLog:
    # XXX: Make this thread safe
    """
    Implements persistent storage of 'currTerm'
    and 'votedFor' state of a DistHash
    """
    def __init__(self, filename) -> None:
        mode = '+wb'
        if os.path.exists(filename):
            # don't need to overwrite logfile if
            # it already exists
            mode = '+rb'
        self.log = open(filename, mode)
        self.currTerm = 0  # latest term server has seen (initialized to 0
                           # on first boot, increases monotonically)
        self.votedFor = -1 # candidateId that received vote in current
                           # term (or null if none)
        self.Lock = threading.Lock()
        self.setCurrTerm(self.currTerm)

    def __del__(self):
        with self.Lock:
            self.log.close()

    class ROSLogInternalError(Exception):
        pass

    def setCurrTerm(self, term : int) -> None:
        with self.Lock:
            ros = ROS(currTerm=term, votedFor = self.votedFor)
            self.log.truncate(0)
            self.log.write(ros.SerializeToString())
            self.currTerm = term

    def getCurrTerm(self) -> int:
        with self.Lock:
            return self.currTerm
    
    def setVotedFor(self, id : id) -> None:
        with self.Lock:
            ros = ROS(currTerm=self.currTerm, votedFor = id)
            self.log.truncate(0)
            self.log.write(ros.SerializeToString())
            self.votedFor = id

    def getVotedFor(self) -> int:
        with self.Lock:
            return self.votedFor


