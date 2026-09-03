from dataclasses import dataclass
from typing import Any

WRITE_TOOLS = {
    "share_quote",
    "update_shipment_status",
}

REQUIRED_ARGUMENTS = {
    "share_quote": [
        "query_id",
    ],
    "update_shipment_status": [
        "query_id",
        "shipment_status",
    ],
}

VALID_STATUSES = {
    "Pending",
    "Booked",
    "In Transit",
    "Delivered",
}


@dataclass
class GuardResult:
    allowed: bool
    message: str | None = None


class ToolGuard:
    """
    Guardrail layer that validates tool calls before execution.
    """

    def validate(
        self,
        user_message: str,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> GuardResult:
        """
        Entry point for validating a tool call.
        """

        # Will be used later for intent validation.
        _ = user_message

        # Read-only tools are always allowed.
        if not self._is_write_tool(tool_name):
            return self._success()

        return self._validate_write_tool(
            tool_name,
            tool_args,
        )

    def _is_write_tool(
        self,
        tool_name: str,
    ) -> bool:
        """
        Determine whether the tool modifies data.
        """
        return tool_name in WRITE_TOOLS

    def _validate_write_tool(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> GuardResult:
        """
        Validate all arguments required for write tools.
        """

        # Required arguments
        result = self._validate_required_arguments(
            tool_name,
            tool_args,
        )

        if not result.allowed:
            return result

        # Query ID
        if "query_id" in tool_args:
            result = self._validate_query_id(
                tool_args["query_id"]
            )

            if not result.allowed:
                return result

        # Shipment Status
        if "shipment_status" in tool_args:
            result = self._validate_status(
                tool_args["shipment_status"]
            )

            if not result.allowed:
                return result

        return self._success()

    def _validate_required_arguments(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
    ) -> GuardResult:
        """
        Ensure all required arguments are present.
        """

        required_args = REQUIRED_ARGUMENTS.get(tool_name, [])

        for arg in required_args:

            if arg not in tool_args:
                return self._failure(
                    f"Missing required argument: '{arg}'."
                )

            if tool_args[arg] is None:
                return self._failure(
                    f"Argument '{arg}' cannot be None."
                )

        return self._success()

    def _validate_query_id(
        self,
        query_id: Any,
    ) -> GuardResult:
        """
        Validate Query ID.
        """

        if not isinstance(query_id, int):
            return self._failure(
                "Query ID must be an integer."
            )

        if query_id <= 0:
            return self._failure(
                "Query ID must be greater than 0."
            )

        return self._success()

    def _validate_status(
        self,
        status: Any,
    ) -> GuardResult:
        """
        Validate shipment status.
        """

        if not isinstance(status, str):
            return self._failure(
                "Shipment status must be a string."
            )
        status = status.strip()

        if not status:
            return self._failure(
                "Shipment status cannot be empty."
            )

        if status not in VALID_STATUSES:
            return self._failure(
                f"Invalid shipment status '{status}'. "
                f"Allowed values are: {', '.join(sorted(VALID_STATUSES))}."
            )

        return self._success()

    def _success(self) -> GuardResult:
        """
        Return a successful validation result.
        """
        return GuardResult(
            allowed=True,
            message=None,
        )

    def _failure(
        self,
        message: str,
    ) -> GuardResult:
        """
        Return a failed validation result.
        """
        return GuardResult(
            allowed=False,
            message=message,
        )