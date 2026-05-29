__artifacts_v2__ = {
    "get_biomeDisplayOrientation": {
        "name": "Biome - Display Orientation",
        "description": "Parses Display Orientation entries from Biome",
        "author": "r.schramp@nfi.nl",
        "version": "0.0.1",
        "date": "2026-05-29",
        "requirements": "none",
        "category": "Biome",
        "notes": "",
        "paths": ('*/Biome/streams/restricted/_DKEvent.Display.Orientation/local/*'),
        "output_types": "standard"
    }
}


import os
from datetime import timezone
import blackboxprotobuf
from scripts.ccl_segb.ccl_segb import read_segb_file
from scripts.ccl_segb.ccl_segb_common import EntryState
from scripts.ilapfuncs import artifact_processor, webkit_timestampsconv, convert_utc_human_to_timezone


@artifact_processor
def get_biomeDisplayOrientation(files_found, report_folder, seeker, wrap_text, timezone_offset):

    # Tested with:
    #  MagnetCTF2026/00008110-0008196A2299401E_files_full.zip
    #  /private/var/mobile/Library/Biome/streams/restricted/_DKEvent.Display.Orientation/local/783965700943629
    #
    # TODO: Validation, the meaning of the orientation int is speculative for now.
    # Reason to add this, is for now it is assumed a physical action is needed.
    #
    # Field mapping:
    #   1  -> Nested message: event descriptor
    #            1.1 -> path string (e.g. "/display/orientation")
    #            1.2 -> identifier pair (1: VARINT, 2: VARINT)
    #   2  -> Timestamp unkn2 (webkit double)
    #   3  -> Timestamp unkn3 (webkit double)
    #   4  -> Nested message: orientation state
    #            4.1 -> identifier pair (mirrors 1.2)
    #            4.4 -> orientation value (0=portrait, 1=landscape)
    #   5  -> GUID string
    #   8  -> Timestamp unkn8 (webkit double)
    #   10 -> VARINT, function TBD (pb_int_10), possibly wrapped negative int64

    typess = {
        '1': {'type': 'message', 'message_typedef': {
            '1': {'type': 'str', 'name': 'event_type'},
            '2': {'type': 'message', 'message_typedef': {
                '1': {'type': 'int', 'name': ''},
                '2': {'type': 'int', 'name': ''}
            }, 'name': 'identifier'}
        }, 'name': 'event_descriptor'},
        '2': {'type': 'double', 'name': 'timestamp_unkn2'},
        '3': {'type': 'double', 'name': 'timestamp_unkn3'},
        '4': {'type': 'message', 'message_typedef': {
            '1': {'type': 'message', 'message_typedef': {
                '1': {'type': 'int', 'name': ''},
                '2': {'type': 'int', 'name': ''}
            }, 'name': 'identifier'},
            '4': {'type': 'int', 'name': 'orientation'}
        }, 'name': 'orientation_state'},
        '5': {'type': 'str',     'name': 'guid'},
        '8': {'type': 'double',  'name': 'timestamp_unkn8'},
        '10': {'type': 'int',    'name': 'pb_int_10'},
    }

    data_list = []
    report_file = 'Unknown'

    for file_found in files_found:
        file_found = str(file_found)
        filename = os.path.basename(file_found)

        if filename.startswith('.'):
            continue
        if os.path.isfile(file_found):
            if 'tombstone' in file_found:
                continue
            else:
                report_file = os.path.dirname(file_found)
        else:
            continue

        for record in read_segb_file(file_found):
            ts = record.timestamp1
            ts = ts.replace(tzinfo=timezone.utc)

            if record.state == EntryState.Written:
                protostuff, types = blackboxprotobuf.decode_message(record.data, typess)

                event_type   = protostuff.get('event_descriptor', {}).get('event_type', '')
                timestamp_unkn2    = webkit_timestampsconv(protostuff['timestamp_unkn2'])
                timestamp_unkn3      = webkit_timestampsconv(protostuff['timestamp_unkn3'])
                orientation  = protostuff.get('orientation_state', {}).get('orientation', None)  # Assumed 0=portrait, 1=landscape
                guid         = protostuff.get('guid', '')
                timestamp_unkn8   = webkit_timestampsconv(protostuff['timestamp_unkn8'])
                pb_int_10    = protostuff.get('pb_int_10', None)

                # Map orientation int to human-readable label
                orientation_label = {0: 'Portrait', 1: 'Landscape'}.get(orientation, f'Unknown ({orientation})')

                data_list.append((
                    ts,
                    record.state.name,
                    orientation_label,
                    guid,
                    timestamp_unkn2,
                #    timestamp_unkn3, in the dataset equal to timestamp_unkn8 but lowres
                #    timestamp_unkn8, in the dataset equal to SEGB timestamp +- miliseconds
                #    pb_int_10, in the dataset allways -18000
                #    event_type, in the dataset allways  /display/orientation
                    filename,
                    record.data_start_offset
                ))

            elif record.state == EntryState.Deleted:
                data_list.append((
                    ts,
                    record.state.name,
                    None,   # orientation_label
                    None,   # guid
                    None,   # timestamp_unkn2
                #    None,   # timestamp_unkn3
                #    None,   # timestamp_unkn8
                #    None,   # pb_int_10
                #    None,   # event_type
                    filename,
                    record.data_start_offset
                ))

    data_headers = (
        ('SEGB Timestamp',   'datetime'),
        'SEGB State',
        'Orientation',
        'GUID',
        ('Timestamp Unkn2',  'datetime'),
#        ('Timestamp Unkn3',  'datetime'),
#        ('Timestamp Unkn8',  'datetime'),
#        'pb_int_10',
#        'Event Type',
        'Filename',
        'Offset'
    )

    return data_headers, data_list, report_file