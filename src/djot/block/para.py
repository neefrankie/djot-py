from dataclasses import dataclass

from ..input import InputText
from ..event import (
    BlockContainer,
    Event,
)
from ..common import Range

from .container import (
    ContainerCap,
    BlockFrame,
    OpenStatus,
    BlockRule,
    OpenResult,
    ParsingContext,
)


@dataclass
class ParaRule(BlockRule):
    kind: ContainerCap = ContainerCap.BLOCK
    accepts_content: ContainerCap = ContainerCap.INLINE

    def try_open(self, cursor: InputText) -> OpenResult:
        container = BlockFrame(
            rule=self,
            start_pos=cursor.pos,
            closing_boundary=Range(cursor.line_end, cursor.line_end)
        )

        pos = cursor.pos
        return OpenResult(
            status=OpenStatus.MATCHED,
            events=[
                Event.enter(
                    kind=BlockContainer.PARA,
                    span=cursor.new_span(pos, pos)
                )
            ],
            frame=container,
            next_pos=pos,
        )

    def on_continue(
        self,
        container: BlockFrame,
        ctx: ParsingContext
    ) -> OpenResult:
        # TODO This won't handle all cases.
        # Lazy content checking is determined in main loop, resulting to inconsistency.
        if not ctx.cursor.peek_is_whitespace():
            container.update_closing_boundary(
                ctx.cursor.line_end,
                ctx.cursor.line_end
            )
            return OpenResult.continue_ok()

        return OpenResult.stop()

    def on_close(
        self, 
        container: BlockFrame, 
        ctx: ParsingContext,
    ) -> OpenResult:
        # Actions performed in djot.js
        # 1. transfer inline matches
        # 2. pop container
        # 3. query last event's endpos
        # 4. emit exit para event.
        assert container.closing_boundary is not None
        return OpenResult(
            status=OpenStatus.CLOSE,
            events=[
                Event.exit(
                    kind=BlockContainer.PARA,
                    span=ctx.cursor.new_span(
                        container.closing_boundary.start,
                        container.closing_boundary.end,
                    )
                )
            ]
        )