# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: disthash.proto
# Protobuf Python Version: 5.26.1
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


from google.protobuf import empty_pb2 as google_dot_protobuf_dot_empty__pb2


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x0e\x64isthash.proto\x12\x08\x64isthash\x1a\x1bgoogle/protobuf/empty.proto\"\x19\n\nGetRequest\x12\x0b\n\x03key\x18\x01 \x01(\t\".\n\x0bGetResponse\x12\r\n\x05value\x18\x01 \x01(\t\x12\x10\n\x08notFound\x18\x02 \x01(\x08\"(\n\nSetRequest\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t\"_\n\x0fRequestVoteArgs\x12\x0c\n\x04term\x18\x01 \x01(\x05\x12\x13\n\x0b\x63\x61ndidateId\x18\x02 \x01(\x05\x12\x14\n\x0clastLogIndex\x18\x03 \x01(\x05\x12\x13\n\x0blastLogTerm\x18\x04 \x01(\x05\"8\n\x13RequestVoteResponse\x12\x0c\n\x04term\x18\x01 \x01(\x05\x12\x13\n\x0bvoteGranted\x18\x02 \x01(\x08\"\xa4\x01\n\x11\x41ppendEntriesArgs\x12\x12\n\nleaderterm\x18\x01 \x01(\x05\x12\x10\n\x08leaderId\x18\x02 \x01(\x05\x12\x14\n\x0cprevLogIndex\x18\x03 \x01(\x05\x12\x13\n\x0bprevLogTerm\x18\x04 \x01(\x05\x12#\n\x07\x65ntries\x18\x05 \x03(\x0b\x32\x12.disthash.LogEntry\x12\x19\n\x11leaderCommitIndex\x18\x06 \x01(\x05\"6\n\x15\x41ppendEntriesResponse\x12\x0c\n\x04term\x18\x01 \x01(\x05\x12\x0f\n\x07success\x18\x02 \x01(\x08\"N\n\x08LogEntry\x12%\n\x07request\x18\x01 \x01(\x0b\x32\x14.disthash.SetRequest\x12\x0c\n\x04term\x18\x02 \x01(\x05\x12\r\n\x05index\x18\x03 \x01(\x05\")\n\x03ROS\x12\x10\n\x08\x63urrTerm\x18\x01 \x01(\x05\x12\x10\n\x08votedFor\x18\x02 \x01(\x05\x32\x93\x02\n\x08\x44istHash\x12\x35\n\x03Set\x12\x14.disthash.SetRequest\x1a\x16.google.protobuf.Empty\"\x00\x12\x34\n\x03Get\x12\x14.disthash.GetRequest\x1a\x15.disthash.GetResponse\"\x00\x12I\n\x0bRequestVote\x12\x19.disthash.RequestVoteArgs\x1a\x1d.disthash.RequestVoteResponse\"\x00\x12O\n\rAppendEntries\x12\x1b.disthash.AppendEntriesArgs\x1a\x1f.disthash.AppendEntriesResponse\"\x00\x62\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'disthash_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_GETREQUEST']._serialized_start=57
  _globals['_GETREQUEST']._serialized_end=82
  _globals['_GETRESPONSE']._serialized_start=84
  _globals['_GETRESPONSE']._serialized_end=130
  _globals['_SETREQUEST']._serialized_start=132
  _globals['_SETREQUEST']._serialized_end=172
  _globals['_REQUESTVOTEARGS']._serialized_start=174
  _globals['_REQUESTVOTEARGS']._serialized_end=269
  _globals['_REQUESTVOTERESPONSE']._serialized_start=271
  _globals['_REQUESTVOTERESPONSE']._serialized_end=327
  _globals['_APPENDENTRIESARGS']._serialized_start=330
  _globals['_APPENDENTRIESARGS']._serialized_end=494
  _globals['_APPENDENTRIESRESPONSE']._serialized_start=496
  _globals['_APPENDENTRIESRESPONSE']._serialized_end=550
  _globals['_LOGENTRY']._serialized_start=552
  _globals['_LOGENTRY']._serialized_end=630
  _globals['_ROS']._serialized_start=632
  _globals['_ROS']._serialized_end=673
  _globals['_DISTHASH']._serialized_start=676
  _globals['_DISTHASH']._serialized_end=951
# @@protoc_insertion_point(module_scope)