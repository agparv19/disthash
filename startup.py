

from concurrent import futures
from disthashServer import DistHashServicer


import argparse
import grpc
import disthash_pb2_grpc
import multiprocessing

WORKER_THREADS = 10

def start_disthash_node(i, ports):
    """
    Start a DistHash Server at {i}th port in {ports}
    """
    if i < 0 or i >= len(ports):
        raise Exception("Out of bound Index")
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=WORKER_THREADS))
    disthash_pb2_grpc.add_DistHashServicer_to_server(DistHashServicer(i, ports), server)
    server.add_insecure_port(f"[::]:{ports[i]}")
    server.start()
    print(f"DistHash node {i} running on port {ports[i]}")
    server.wait_for_termination()
    

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--ports',
                        type = int,
                        nargs = '+',
                        required = True,
                        help = "A list of ports to run DistHash nodes")
    args = parser.parse_args()
    ports = args.ports

    processes = []
    for i, port in enumerate(ports):
        process = multiprocessing.Process(target=start_disthash_node, args=(i,ports))
        processes.append(process)
        process.start()

    for process in processes:
        process.join()

if __name__ == "__main__":
    main()