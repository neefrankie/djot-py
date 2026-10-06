from .parser import EventParser


def parse_events(input_: str):
    parser = EventParser(input_)
    yield from parser.parse()