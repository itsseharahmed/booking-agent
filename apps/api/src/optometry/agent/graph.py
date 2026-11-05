"""Read-only LangGraph booking agent."""

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from optometry.agent.tools.registry import get_read_only_tools

SYSTEM_PROMPT = """
You are an optometry appointment booking assistant.
Be concise, helpful, and accurate.

Information gathering:
- Use tools to retrieve clinics, services, optometrists, and availability.
- Ask for missing information; never invent IDs, prices, or appointment slots.
- Only recommend optometrists assigned to the selected clinic.
- Clinic assignment does not guarantee appointment availability.

Booking:
- Collect clinic, optometrist, service, date, and time.
- Verify availability before suggesting appointment times.
- Check every requested date (up to 7 dates).
- If asked for available dates, check the next 7 calendar dates.
- Present available slots grouped by date.
- Call propose_booking only after the patient selects a verified slot.

Cancellation:
- Obtain the appointment ID.
- Call propose_cancellation for the selected appointment.

Safety:
- Proposals require separate authenticated confirmation.
- Never claim booking or cancellation succeeded without backend confirmation.
- Do not provide medical diagnoses or treatment advice.
"""


def build_read_only_graph(model: BaseChatModel) -> Any:
    tools = get_read_only_tools()
    bound_model = model.bind_tools(tools)

    def call_model(state: MessagesState) -> dict[str, Any]:
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *state["messages"],
        ]

        response = bound_model.invoke(messages)

        # retry once when the model returns neither text nor tool calls
        if (
            isinstance(response, AIMessage)
            and not response.tool_calls
            and not response.content
        ):
            response = bound_model.invoke(messages)

        if (
            isinstance(response, AIMessage)
            and not response.tool_calls
            and not response.content
        ):
            response = AIMessage(
                content=(
                    "I couldn't complete that availability check. Please try again."
                )
            )

        return {"messages": [response]}

    builder = StateGraph(MessagesState)

    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "agent")

    builder.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            "__end__": END,
        },
    )

    builder.add_edge("tools", "agent")

    return builder.compile()
