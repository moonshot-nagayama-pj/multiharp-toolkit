from typing import TypeAlias, TypedDict
import pyarrow as pa
from pyarrow import RecordBatch
import multiharp_toolkit._mhtk_rs as mh

T2WRAPAROUND_V1 = 33552000
T2WRAPAROUND_V2 = 33554432

Channel: TypeAlias = int
"""channel number. usually sync ch is 0."""

TimeTag: TypeAlias = float
"""time in ps"""

RawMeasData: TypeAlias = int


TimeTagDataSchema = pa.schema([("ch", pa.int8()), ("timestamp", pa.float64())])


class DeviceInputChannelConfig(TypedDict):
    edge_trigger_level: int
    edge_trigger: "mh.Edge"
    channel_offset: int
    enable: bool


class DeviceConfig(TypedDict):
    sync_divider: int
    sync_edge_trigger_level: int  # mV
    sync_edge: "mh.Edge"
    sync_channel_offset: int  # ps
    sync_channel_enable: bool
    inputs: list[DeviceInputChannelConfig]


class MeasStartMarker:
    config: DeviceConfig
    measurement_duration: float
    param: dict[str, str | int | float]

    def __init__(
        self,
        config: DeviceConfig,
        measurement_duration: float,
        param: dict[str, str | int | float] = {},
    ) -> None:
        self.config = config
        self.measurement_duration = measurement_duration
        self.param = param


class MeasEndMarker:
    pass


RawMeasDataSequence: TypeAlias = list[RawMeasData | MeasEndMarker | MeasStartMarker]
ParsedMeasDataSequence: TypeAlias = "RecordBatch | MeasEndMarker | MeasStartMarker"
