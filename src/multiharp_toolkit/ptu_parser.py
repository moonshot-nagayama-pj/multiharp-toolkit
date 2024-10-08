# based on MultiHarp150_160_V3_1 from https://www.picoquant.com/products/category/tcspc-and-time-tagging-modules/multiharp-160#custom1
#
# Read_PTU.py    Read PicoQuant Unified Histogram Files
# This is demo code. Use at your own risk. No warranties.
# Keno Goertz, PicoQUant GmbH, February 2018

import time, sys, struct, io
from typing import Any


# Tag Types
tyEmpty8 = struct.unpack(">i", bytes.fromhex("FFFF0008"))[0]
tyBool8 = struct.unpack(">i", bytes.fromhex("00000008"))[0]
tyInt8 = struct.unpack(">i", bytes.fromhex("10000008"))[0]
tyBitSet64 = struct.unpack(">i", bytes.fromhex("11000008"))[0]
tyColor8 = struct.unpack(">i", bytes.fromhex("12000008"))[0]
tyFloat8 = struct.unpack(">i", bytes.fromhex("20000008"))[0]
tyTDateTime = struct.unpack(">i", bytes.fromhex("21000008"))[0]
tyFloat8Array = struct.unpack(">i", bytes.fromhex("2001FFFF"))[0]
tyAnsiString = struct.unpack(">i", bytes.fromhex("4001FFFF"))[0]
tyWideString = struct.unpack(">i", bytes.fromhex("4002FFFF"))[0]
tyBinaryBlob = struct.unpack(">i", bytes.fromhex("FFFFFFFF"))[0]


class TimeTaggedData:
    names: list[str]
    values: list[Any]
    numRecords: int
    globRes: float
    events: list[list[int | float]]  # [channel: [timetag]]


class Parser:
    events: list[list[int | float]]  # [channel: [timetag]]
    timestamps: list[float]  # for combined channel mode
    channels: list[int]  # for combined channel mode
    oflcorrection: int
    ptu_version: int
    T2WRAPAROUND_V1 = 33552000
    T2WRAPAROUND_V2 = 33554432
    combined_channel = bool

    def __init__(self, ptu_version=2) -> None:
        self.oflcorrection = 0
        self.ptu_version = ptu_version
        self.events = [[] for i in range(0, 65)]  # max 64ch
        self.channels = []
        self.timestamps = []
        self.combined_channel = False
        self.time_resolution = 5

    def __repr__(self) -> str:
        num_ev_str = ",".join(
            [
                f"{ch}:{len(events)}events"
                for ch, events in enumerate(self.events)
                if len(events) > 0
            ]
        )
        return f"Parser(events: {num_ev_str}, v{self.ptu_version}, ofl: {self.oflcorrection})"

    def reset(self):
        self.oflcorrection = 0
        self.channels = []
        self.timestamps = []
        self.events = [[] for i in range(0, 65)]  # max 64ch

    def parse_records(self, inputfile: io.BufferedReader, num_records: int):
        for i in range(0, num_records):
            data = struct.unpack("<I", inputfile.read(4))[0]
            self.parse_record(data)
            if i % 100000 == 0:
                sys.stdout.write(
                    "\rLoading file: %.1f%%" % (float(i) * 100 / float(num_records))
                )
                sys.stdout.flush()

    def parse_record(self, data: int):
        special = (data >> 31) & 0x01  # 最上位ビット
        channel = (data >> 25) & 0x3F  # 次の6ビット
        timetag = data & 0x1FFFFFF
        if special == 1:
            if channel == 0x3F:  # Overflow
                # Number of overflows in nsync. If old version, it's an
                # old style single overflow
                if self.ptu_version == 1:
                    self.oflcorrection += Parser.T2WRAPAROUND_V1
                else:
                    if timetag == 0:  # old style overflow, shouldn't happen
                        self.oflcorrection += Parser.T2WRAPAROUND_V2
                    else:
                        self.oflcorrection += Parser.T2WRAPAROUND_V2 * timetag
            # if channel >= 1 and channel <= 15: # markers
            #     truetime = oflcorrection + timetag
            if channel == 0:  # sync
                truetime = self.oflcorrection + timetag
                self.append_events(0, truetime)
        else:  # regular input channel
            truetime = self.oflcorrection + timetag
            self.append_events(channel + 1, truetime)

    def convert_timetag_to_relative_timestamp(self, timetag: int) -> int:
        """convert time tag to time(unit: psec)
        """
        return timetag * self.time_resolution

    def append_events(self, channel: int, timestamp: int):
        if self.combined_channel:
            self.channels.append(channel)
            self.timestamps.append(self.convert_timetag_to_relative_timestamp(timestamp))
        else:
            self.events[channel].append(self.convert_timetag_to_relative_timestamp(timestamp))


def parse_header(inputfile: io.BufferedReader):
    magic = inputfile.read(8).decode("utf-8").strip("\0")
    if magic != "PQTTTR":
        print("ERROR: Magic invalid, this is not a PTU file.")
        return None

    # e.g. 1.1.02
    version = inputfile.read(8).decode("utf-8").strip("\0")
    # Write the header data to outputfile and also save it in memory.
    # There's no do ... while in Python, so an if statement inside the while loop
    # breaks out of it
    tagDataList = []  # Contains tuples of (tagName, tagValue)
    while True:
        tagIdent = inputfile.read(32).decode("utf-8").strip("\0")
        tagIdx = struct.unpack("<i", inputfile.read(4))[0]
        tagTyp = struct.unpack("<i", inputfile.read(4))[0]
        if tagIdx > -1:
            evalName = tagIdent + "(" + str(tagIdx) + ")"
        else:
            evalName = tagIdent
        # outputfile.write("\n%-40s" % evalName)
        if tagTyp == tyEmpty8:
            inputfile.read(8)
            # outputfile.write("<empty Tag>")
            tagDataList.append((evalName, "<empty Tag>"))
        elif tagTyp == tyBool8:
            tagInt = struct.unpack("<q", inputfile.read(8))[0]
            if tagInt == 0:
                # outputfile.write("False")
                tagDataList.append((evalName, "False"))
            else:
                # outputfile.write("True")
                tagDataList.append((evalName, "True"))
        elif tagTyp == tyInt8:
            tagInt = struct.unpack("<q", inputfile.read(8))[0]
            # outputfile.write("%d" % tagInt)
            tagDataList.append((evalName, tagInt))
        elif tagTyp == tyBitSet64:
            tagInt = struct.unpack("<q", inputfile.read(8))[0]
            # outputfile.write("{0:#0{1}x}".format(tagInt,18))
            tagDataList.append((evalName, tagInt))
        elif tagTyp == tyColor8:
            tagInt = struct.unpack("<q", inputfile.read(8))[0]
            # outputfile.write("{0:#0{1}x}".format(tagInt,18))
            tagDataList.append((evalName, tagInt))
        elif tagTyp == tyFloat8:
            tagFloat = struct.unpack("<d", inputfile.read(8))[0]
            # outputfile.write("%-3E" % tagFloat)
            tagDataList.append((evalName, tagFloat))
        elif tagTyp == tyFloat8Array:
            tagInt = struct.unpack("<q", inputfile.read(8))[0]
            # outputfile.write("<Float array with %d entries>" % tagInt/8)
            tagDataList.append((evalName, tagInt))
        elif tagTyp == tyTDateTime:
            tagFloat = struct.unpack("<d", inputfile.read(8))[0]
            tagTime = int((tagFloat - 25569) * 86400)
            tagTime = time.gmtime(tagTime)
            # outputfile.write(time.strftime("%a %b %d %H:%M:%S %Y", tagTime))
            tagDataList.append((evalName, tagTime))
        elif tagTyp == tyAnsiString:
            tagInt = struct.unpack("<q", inputfile.read(8))[0]
            tagString = inputfile.read(tagInt).decode("utf-8").strip("\0")
            # outputfile.write("%s" % tagString)
            tagDataList.append((evalName, tagString))
        elif tagTyp == tyWideString:
            tagInt = struct.unpack("<q", inputfile.read(8))[0]
            tagString = (
                inputfile.read(tagInt).decode("utf-16le", errors="ignore").strip("\0")
            )
            # outputfile.write(tagString)
            tagDataList.append((evalName, tagString))
        elif tagTyp == tyBinaryBlob:
            tagInt = struct.unpack("<q", inputfile.read(8))[0]
            # outputfile.write("<Binary blob with %d bytes>" % tagInt)
            tagDataList.append((evalName, tagInt))
        else:
            print("ERROR: Unknown tag type", tagTyp)
            exit(0)
        if tagIdent == "Header_End":
            break

    # Reformat the saved data for easier access
    return [tagDataList[i][0] for i in range(0, len(tagDataList))], [
        tagDataList[i][1] for i in range(0, len(tagDataList))
    ]


def parse(inputfile: io.BufferedReader) -> TimeTaggedData | None:
    headers = parse_header(inputfile)
    assert headers is not None, "failed to parse header"
    tagNames, tagValues = headers
    ret = TimeTaggedData()
    ret.names = tagNames
    ret.values = tagValues
    ret.events = [[] for i in range(0, 65)]

    # get important variables from headers
    ret.numRecords = tagValues[tagNames.index("TTResult_NumberOfRecords")]
    ret.globRes = tagValues[tagNames.index("MeasDesc_GlobalResolution")]
    print({"globRes": ret.globRes, "numRecords": ret.numRecords})

    ctx = Parser(ptu_version=2)
    ctx.parse_records(inputfile, ret.numRecords)
    ret.events = ctx.events
    return ret
