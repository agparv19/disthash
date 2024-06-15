from disthash_pb2 import LogEntry
import os
import sys
import threading

class WALog:
    # XXX: Make this thread safe
    """
    Implements Write ahead logging (WAL) features.
    """
    def __init__(self, filename : str) -> None:
        mode = '+wb'
        if os.path.exists(filename):
            # don't need to overwrite logfile if
            # it already exists
            mode = '+rb'
        self.log = open(filename, mode)
        self.lastIndex = 0 # index of last LogEntry appended to log
        self.lastTerm = 0  # term of last LogEntry appended to log
        self.offsets = {} # stores offsets of each index from
                          # start of the file
        self.Lock = threading.Lock()
        self._populateOffsets()

    def __del__(self):
        with self.Lock:
            self.log.close()

    def getLastIndex(self):
        with self.Lock:
            return self.lastIndex
    
    def getLastTerm(self):
        with self.Lock:
            return self.lastTerm

    def _populateOffsets(self) -> None:
        """
        Seeks over existing entries to populate offsets dict.
        """
        with self.Lock:
            # ensure log filehandle is at the start
            self.log.seek(0, 0)
            while True:
                pos = self.log.tell()
                entrySizeb = self.log.read(4)
                if not entrySizeb:
                    # no more entries left
                    break
                entrySize = int.from_bytes(entrySizeb, byteorder=sys.byteorder)
                self.lastIndex += 1
                self.offsets[self.lastIndex] = pos

                # seek ahead to the next entry
                self.log.seek(entrySize, 1)


    def appendEntry(self, entry : LogEntry) -> int:
        """
        Returns the index of the newly appended entry.
        """
        with self.Lock:
            self.lastIndex += 1
            entry.index = self.lastIndex
            
            # ensure log filehandle is at the
            # end of file
            self.log.seek(0, os.SEEK_END)
            
            # store location of this entry in log
            self.offsets[self.lastIndex] = self.log.tell()

            # write the length + data
            data2dump = entry.SerializeToString()
            self.log.write(len(data2dump).to_bytes(4, byteorder=sys.byteorder))
            self.log.write(data2dump)
            self.lastTerm = entry.term

            return self.lastIndex

    class IndexNotFound(Exception):
        pass

    class WALogInternalError(Exception):
        pass

    def readEntry(self, n) -> LogEntry:
        """
        Returns {n}th entry from the log.
        """
        with self.Lock:
            if n not in self.offsets:
                raise self.IndexNotFound()
            
            # seek to location of nth LogEntry
            self.log.seek(self.offsets[n], 0)

            # read length
            entrySizeb = self.log.read(4)

            if not entrySizeb:
                raise self.WALogInternalError("Unable to read size of LogEntry")
            
            entrySize = int.from_bytes(entrySizeb, byteorder=sys.byteorder)
            entryb = self.log.read(entrySize)

            if not entryb:
                raise self.WALogInternalError("Unable to read LogEntry")

            entry = LogEntry()
            entry.ParseFromString(entryb)
            return entry
    
    def deleteAhead(self, n) -> None:
        """
        deletes all log entries from index n till the last index
        """
        with self.Lock:
            # seek to location of nth LogEntry
            self.log.seek(self.offsets[n], 0)

            # remove everything ahead of it
            self.log.truncate()

            # clear out offsets for n till the end
            key = n
            while (key <= self.lastIndex):
                self.offsets.pop(key)
                key += 1
            
            # now the log contains entries only till (n-1) th index
            self.lastIndex = n-1

