"""
Usage: python3 disthashClient -p <port> -key <key> -value <value>
"""

import disthash_pb2_grpc
import disthash_pb2
import grpc
import argparse


def main():
    parser = argparse.ArgumentParser(description="A client script to talk to DistHash server using gRPC") 
    parser.add_argument("-p", "--port", required=True)
    parser.add_argument("--key", required=True)
    parser.add_argument("--value", required=False)
    args = parser.parse_args()

    channel = grpc.insecure_channel(f"localhost:{args.port}")
    client = disthash_pb2_grpc.DistHashStub(channel)
    if args.value:
        # this is a set request
        set_request = disthash_pb2.SetRequest(key = args.key, value = args.value)
        client.Set(set_request)
    else:
        # this is a get request
        get_request = disthash_pb2.GetRequest(key = args.key)
        res = client.Get(get_request)
        if res.notFound:
            print(f"key {args.key} d.n.e!")
        else:
            print(f"value: {res.value}")

if __name__ == '__main__':
    main()


