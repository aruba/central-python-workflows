# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: audit.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='audit.proto',
  package='Audit',
  syntax='proto2',
  serialized_options=None,
  serialized_pb=_b('\n\x0b\x61udit.proto\x12\x05\x41udit\"\x1b\n\x0bmac_address\x12\x0c\n\x04\x61\x64\x64r\x18\x01 \x01(\x0c\"\x99\x01\n\nip_address\x12)\n\x02\x61\x66\x18\x01 \x01(\x0e\x32\x1d.Audit.ip_address.addr_family\x12\x0c\n\x04\x61\x64\x64r\x18\x02 \x01(\x0c\"R\n\x0b\x61\x64\x64r_family\x12\x16\n\x12\x41\x44\x44R_FAMILY_UNSPEC\x10\x00\x12\x14\n\x10\x41\x44\x44R_FAMILY_INET\x10\x01\x12\x15\n\x11\x41\x44\x44R_FAMILY_INET6\x10\x02\"-\n\x06\x63onfig\x12\x0c\n\x04\x64\x61ta\x18\x01 \x02(\t\x12\x15\n\rdetailed_data\x18\x02 \x01(\t\"/\n\x08\x66irmware\x12\x0c\n\x04\x64\x61ta\x18\x01 \x02(\t\x12\x15\n\rdetailed_data\x18\x02 \x01(\t\"8\n\x11\x64\x65vice_management\x12\x0c\n\x04\x64\x61ta\x18\x01 \x02(\t\x12\x15\n\rdetailed_data\x18\x02 \x01(\t\"\xb2\x02\n\raudit_message\x12\x13\n\x0b\x63ustomer_id\x18\x01 \x02(\t\x12\x11\n\ttimestamp\x18\x02 \x02(\r\x12&\n\x07service\x18\x03 \x02(\x0e\x32\x15.Audit.classification\x12\x12\n\ngroup_name\x18\x04 \x02(\t\x12\x0e\n\x06target\x18\x05 \x02(\t\x12$\n\tclient_ip\x18\x06 \x02(\x0b\x32\x11.Audit.ip_address\x12\x10\n\x08username\x18\x07 \x02(\t\x12\"\n\x0b\x63onfig_info\x18\x08 \x01(\x0b\x32\r.Audit.config\x12&\n\rfirmware_info\x18\t \x01(\x0b\x32\x0f.Audit.firmware\x12)\n\x07\x64m_info\x18\x10 \x01(\x0b\x32\x18.Audit.device_management*B\n\x0e\x63lassification\x12\x11\n\rCONFIGURATION\x10\x00\x12\x0c\n\x08\x46IRMWARE\x10\x01\x12\x0f\n\x0b\x44\x45VICE_MGMT\x10\x02')
)

_CLASSIFICATION = _descriptor.EnumDescriptor(
  name='classification',
  full_name='Audit.classification',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='CONFIGURATION', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FIRMWARE', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DEVICE_MGMT', index=2, number=2,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=670,
  serialized_end=736,
)
_sym_db.RegisterEnumDescriptor(_CLASSIFICATION)

classification = enum_type_wrapper.EnumTypeWrapper(_CLASSIFICATION)
CONFIGURATION = 0
FIRMWARE = 1
DEVICE_MGMT = 2


_IP_ADDRESS_ADDR_FAMILY = _descriptor.EnumDescriptor(
  name='addr_family',
  full_name='Audit.ip_address.addr_family',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='ADDR_FAMILY_UNSPEC', index=0, number=0,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ADDR_FAMILY_INET', index=1, number=1,
      serialized_options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='ADDR_FAMILY_INET6', index=2, number=2,
      serialized_options=None,
      type=None),
  ],
  containing_type=None,
  serialized_options=None,
  serialized_start=123,
  serialized_end=205,
)
_sym_db.RegisterEnumDescriptor(_IP_ADDRESS_ADDR_FAMILY)


_MAC_ADDRESS = _descriptor.Descriptor(
  name='mac_address',
  full_name='Audit.mac_address',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='addr', full_name='Audit.mac_address.addr', index=0,
      number=1, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=22,
  serialized_end=49,
)


_IP_ADDRESS = _descriptor.Descriptor(
  name='ip_address',
  full_name='Audit.ip_address',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='af', full_name='Audit.ip_address.af', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='addr', full_name='Audit.ip_address.addr', index=1,
      number=2, type=12, cpp_type=9, label=1,
      has_default_value=False, default_value=_b(""),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _IP_ADDRESS_ADDR_FAMILY,
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=52,
  serialized_end=205,
)


_CONFIG = _descriptor.Descriptor(
  name='config',
  full_name='Audit.config',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='data', full_name='Audit.config.data', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='detailed_data', full_name='Audit.config.detailed_data', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=207,
  serialized_end=252,
)


_FIRMWARE = _descriptor.Descriptor(
  name='firmware',
  full_name='Audit.firmware',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='data', full_name='Audit.firmware.data', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='detailed_data', full_name='Audit.firmware.detailed_data', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=254,
  serialized_end=301,
)


_DEVICE_MANAGEMENT = _descriptor.Descriptor(
  name='device_management',
  full_name='Audit.device_management',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='data', full_name='Audit.device_management.data', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='detailed_data', full_name='Audit.device_management.detailed_data', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=303,
  serialized_end=359,
)


_AUDIT_MESSAGE = _descriptor.Descriptor(
  name='audit_message',
  full_name='Audit.audit_message',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='customer_id', full_name='Audit.audit_message.customer_id', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='timestamp', full_name='Audit.audit_message.timestamp', index=1,
      number=2, type=13, cpp_type=3, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='service', full_name='Audit.audit_message.service', index=2,
      number=3, type=14, cpp_type=8, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='group_name', full_name='Audit.audit_message.group_name', index=3,
      number=4, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='target', full_name='Audit.audit_message.target', index=4,
      number=5, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='client_ip', full_name='Audit.audit_message.client_ip', index=5,
      number=6, type=11, cpp_type=10, label=2,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='username', full_name='Audit.audit_message.username', index=6,
      number=7, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='config_info', full_name='Audit.audit_message.config_info', index=7,
      number=8, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='firmware_info', full_name='Audit.audit_message.firmware_info', index=8,
      number=9, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='dm_info', full_name='Audit.audit_message.dm_info', index=9,
      number=16, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      serialized_options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  serialized_options=None,
  is_extendable=False,
  syntax='proto2',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=362,
  serialized_end=668,
)

_IP_ADDRESS.fields_by_name['af'].enum_type = _IP_ADDRESS_ADDR_FAMILY
_IP_ADDRESS_ADDR_FAMILY.containing_type = _IP_ADDRESS
_AUDIT_MESSAGE.fields_by_name['service'].enum_type = _CLASSIFICATION
_AUDIT_MESSAGE.fields_by_name['client_ip'].message_type = _IP_ADDRESS
_AUDIT_MESSAGE.fields_by_name['config_info'].message_type = _CONFIG
_AUDIT_MESSAGE.fields_by_name['firmware_info'].message_type = _FIRMWARE
_AUDIT_MESSAGE.fields_by_name['dm_info'].message_type = _DEVICE_MANAGEMENT
DESCRIPTOR.message_types_by_name['mac_address'] = _MAC_ADDRESS
DESCRIPTOR.message_types_by_name['ip_address'] = _IP_ADDRESS
DESCRIPTOR.message_types_by_name['config'] = _CONFIG
DESCRIPTOR.message_types_by_name['firmware'] = _FIRMWARE
DESCRIPTOR.message_types_by_name['device_management'] = _DEVICE_MANAGEMENT
DESCRIPTOR.message_types_by_name['audit_message'] = _AUDIT_MESSAGE
DESCRIPTOR.enum_types_by_name['classification'] = _CLASSIFICATION
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

mac_address = _reflection.GeneratedProtocolMessageType('mac_address', (_message.Message,), dict(
  DESCRIPTOR = _MAC_ADDRESS,
  __module__ = 'audit_pb2'
  # @@protoc_insertion_point(class_scope:Audit.mac_address)
  ))
_sym_db.RegisterMessage(mac_address)

ip_address = _reflection.GeneratedProtocolMessageType('ip_address', (_message.Message,), dict(
  DESCRIPTOR = _IP_ADDRESS,
  __module__ = 'audit_pb2'
  # @@protoc_insertion_point(class_scope:Audit.ip_address)
  ))
_sym_db.RegisterMessage(ip_address)

config = _reflection.GeneratedProtocolMessageType('config', (_message.Message,), dict(
  DESCRIPTOR = _CONFIG,
  __module__ = 'audit_pb2'
  # @@protoc_insertion_point(class_scope:Audit.config)
  ))
_sym_db.RegisterMessage(config)

firmware = _reflection.GeneratedProtocolMessageType('firmware', (_message.Message,), dict(
  DESCRIPTOR = _FIRMWARE,
  __module__ = 'audit_pb2'
  # @@protoc_insertion_point(class_scope:Audit.firmware)
  ))
_sym_db.RegisterMessage(firmware)

device_management = _reflection.GeneratedProtocolMessageType('device_management', (_message.Message,), dict(
  DESCRIPTOR = _DEVICE_MANAGEMENT,
  __module__ = 'audit_pb2'
  # @@protoc_insertion_point(class_scope:Audit.device_management)
  ))
_sym_db.RegisterMessage(device_management)

audit_message = _reflection.GeneratedProtocolMessageType('audit_message', (_message.Message,), dict(
  DESCRIPTOR = _AUDIT_MESSAGE,
  __module__ = 'audit_pb2'
  # @@protoc_insertion_point(class_scope:Audit.audit_message)
  ))
_sym_db.RegisterMessage(audit_message)


# @@protoc_insertion_point(module_scope)
