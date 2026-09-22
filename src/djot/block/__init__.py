from .parser import EventParser
from ..options import Options


def parse_events(input_: str, options: Options):
    parser = EventParser(input_, options)
    yield from parser.parse()