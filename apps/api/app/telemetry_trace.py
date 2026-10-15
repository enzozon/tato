from time import time_ns
from typing import TYPE_CHECKING
from uuid import uuid4

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, InstrumentationScope, KeyValue
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

if TYPE_CHECKING:
    from app.telemetry import TechnicalEvent


def encode_trace(event: "TechnicalEvent") -> bytes:
    ended = time_ns()
    attributes = []
    for key, value in event.model_dump(exclude_none=True, exclude={"event"}).items():
        attribute = (
            AnyValue(int_value=value) if isinstance(value, int) else AnyValue(string_value=value)
        )
        attributes.append(KeyValue(key=key, value=attribute))
    span = Span(
        trace_id=uuid4().bytes,
        span_id=uuid4().bytes[:8],
        name=event.event,
        kind=Span.SPAN_KIND_INTERNAL,
        start_time_unix_nano=ended - (event.elapsed_ms or 0) * 1_000_000,
        end_time_unix_nano=ended,
        attributes=attributes,
    )
    request = ExportTraceServiceRequest(
        resource_spans=[
            ResourceSpans(
                resource=Resource(
                    attributes=[
                        KeyValue(key="service.name", value=AnyValue(string_value="tato-api"))
                    ]
                ),
                scope_spans=[
                    ScopeSpans(scope=InstrumentationScope(name="tato.technical"), spans=[span])
                ],
            )
        ]
    )
    payload: bytes = request.SerializeToString()
    return payload
