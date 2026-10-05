"""Helper utilities for Pydantic validation with Flask requests.

This module provides helpers to unify validation of JSON and multipart/form-data
requests using Pydantic models, avoiding code duplication.
"""

import json
from typing import TypeVar, Type, Tuple, Optional
from flask import Request
from pydantic import BaseModel, ValidationError

from web.errors import error_response

T = TypeVar("T", bound=BaseModel)


def validate_request_data(
    request: Request, model_class: Type[T], context: str = ""
) -> Tuple[Optional[T], Optional[Tuple]]:
    """
    Validate request data (JSON or multipart/form-data) using Pydantic model.

    This helper unifies validation for both JSON and multipart/form-data requests,
    avoiding code duplication in endpoints.

    Args:
        request: Flask request object
        model_class: Pydantic model class to validate against
        context: Optional context string for error logging

    Returns:
        Tuple of (validated_model, error_response):
        - (model_instance, None) if validation succeeds
        - (None, (jsonify_response, status_code)) if validation fails

    Example:
        ```python
        data, error = validate_request_data(request, PetCreate)
        if error:
            return error
        # Use data.name, data.birth_date, etc.
        ```
    """
    try:
        # Check if request is multipart/form-data
        if request.content_type and "multipart/form-data" in request.content_type:
            # Validate form data
            data_dict = request.form.to_dict()
            # Parse JSON strings in form data (e.g., tiles_settings)
            for key, value in data_dict.items():
                if isinstance(value, str) and (value.startswith("{") or value.startswith("[")):
                    try:
                        data_dict[key] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        pass  # Keep as string if not valid JSON
            validated_data = model_class.model_validate(data_dict)
        else:
            # Validate JSON data
            json_data = request.get_json()
            if json_data is None:
                return None, error_response("validation_error")
            validated_data = model_class.model_validate(json_data)

        return validated_data, None

    except ValidationError as e:
        # Pydantic validation errors are handled by the global error handler
        # but we return a generic validation error here for consistency
        if context:
            from web.app import logger

            logger.warning(f"Validation error in {context}: {e}")

        # The first problem, in Russian (the same wording as JSON requests).
        from web.validation import message_for

        return None, error_response("validation_error", message_for(e.errors()))
    except Exception as e:
        # Handle other unexpected errors
        if context:
            from web.app import logger

            logger.warning(f"Unexpected error validating {context}: {e}")
        return None, error_response("validation_error", str(e))


def form_value(values: list):
    """One field of a multipart form as the model should get it.

    The library that validates the request read every single value as JSON (``json.loads``), so a pet named «7», a document
    titled «2025» or a note of «true» or «null» arrived as a number, a boolean or nothing and was refused with a generic
    message. Text stays text; only what is plainly an object or a list («{…}», «[…]», the tiles of a pet) is decoded.
    """
    if len(values) != 1:
        return values
    value = values[0]
    if isinstance(value, str) and value.startswith(("{", "[")):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass
    return value


def parse_multi_dict_as_text(input) -> dict:
    """``flask_pydantic_spec.utils.parse_multi_dict`` with text left as text (see ``form_value``)."""
    return {key: form_value(values) for key, values in input.to_dict(flat=False).items()}


def keep_form_text_as_text() -> None:
    """Replace the multipart reader of the validation library in the one place that calls it."""
    from flask_pydantic_spec import flask_backend

    flask_backend.parse_multi_dict = parse_multi_dict_as_text
