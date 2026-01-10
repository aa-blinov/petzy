from functools import wraps
from flask import request, g
from bson import ObjectId

from web.security import get_current_user, login_required
from web.helpers import validate_pet_access, get_record_and_validate_access

def require_pet_access(f):
    """
    Decorator to check authentication and pet access.
    Expects 'pet_id' to be present in request query params, body (via context), or args.
    Sets g.username upon success.
    """
    @login_required
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Authentication
        username, auth_error = get_current_user()
        if auth_error:
            return auth_error[0], auth_error[1]
        
        # 2. Extract pet_id
        pet_id = None
        
        # Check context (flask-pydantic-spec)
        if hasattr(request, 'context'):
            # Try query
            if hasattr(request.context, 'query') and hasattr(request.context.query, 'pet_id'):
                pet_id = request.context.query.pet_id
            # Try body
            elif hasattr(request.context, 'body') and hasattr(request.context.body, 'pet_id'):
                pet_id = request.context.body.pet_id

        # Fallback to pure request args if not found in context (e.g. if not validated yet or mixed)
        if not pet_id:
            pet_id = request.args.get("pet_id")

        # 3. Validate Access
        success, access_error = validate_pet_access(pet_id, username)
        if not success:
            # error_response helper returns (json, status_code)
            return access_error[0], access_error[1]
            
        # 4. Set Context
        g.username = username
        g.pet_id = pet_id
        
        return f(*args, **kwargs)
    return decorated_function

def require_record_access(collection_name):
    """
    Decorator to check authentication and access to a specific record.
    The record_id must be the FIRST positional argument or 'id'/'record_id' keyword argument.
    Sets g.username, g.record, g.pet_id upon success.
    """
    def decorator(f):
        @login_required
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1. Authentication
            username, auth_error = get_current_user()
            if auth_error:
                return auth_error[0], auth_error[1]

            # 2. Extract record_id
            # Flask passes path variables as kwargs usually
            record_id = kwargs.get('record_id') or kwargs.get('id')
            if not record_id and args:
                # If passed as positional (unlikely with named routes but possible)
                record_id = args[0]
            
            # 3. Validate Record Access
            # get_record_and_validate_access handles validation of record_id string too
            record, pet_id, access_error = get_record_and_validate_access(record_id, collection_name, username)
            if access_error:
                return access_error[0], access_error[1]
            
            # 4. Set Context
            g.username = username
            g.record = record
            g.pet_id = pet_id
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator
