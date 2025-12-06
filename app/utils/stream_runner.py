"""
Stream runner utility for real-time command output via Server-Sent Events.
"""
import subprocess
import json
import shlex
from flask import Response
import config
from app.utils.logger import get_tools_logger

logger = get_tools_logger()


def run_command_with_stream(cmd, task_id):
    """
    Run a command and stream output via Server-Sent Events.
    
    Args:
        cmd: Command to execute (as list of arguments - required for security)
        task_id: Unique identifier for this task
    
    Returns:
        Flask Response with SSE stream
    """
    def generate():
        try:
            # Build command safely - cmd must be a list
            if not isinstance(cmd, list):
                raise ValueError("Command must be a list of arguments for security")
            
            # Construct the full command with conda wrapper
            full_cmd = ['conda', 'run', '-n', config.CONDA_ENV] + cmd
            
            logger.info(f"Streaming command: {' '.join(shlex.quote(c) for c in full_cmd)}")
            
            process = subprocess.Popen(
                full_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            for line in iter(process.stdout.readline, ''):
                if line:
                    data = json.dumps({
                        'line': line.rstrip('\n'),
                        'task_id': task_id
                    })
                    yield f"data: {data}\n\n"
            
            process.wait()
            
            # Send completion event
            data = json.dumps({
                'done': True,
                'returncode': process.returncode,
                'task_id': task_id
            })
            yield f"data: {data}\n\n"
            
        except Exception as e:
            logger.error(f"Stream error: {str(e)}")
            data = json.dumps({
                'error': str(e),
                'done': True,
                'returncode': -1,
                'task_id': task_id
            })
            yield f"data: {data}\n\n"
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


def run_pipeline_step_with_stream(step_func, args, task_id, enable_progress=False):
    """
    Run a pipeline step function and stream progress updates.
    
    Args:
        step_func: The step function to execute
        args: Arguments for the step function
        task_id: Unique identifier for this task
        enable_progress: If True, pass a progress_callback to the step function
    
    Returns:
        Flask Response with SSE stream
    """
    def generate():
        try:
            # Send start event
            yield f"data: {json.dumps({'status': 'started', 'task_id': task_id})}\n\n"
            
            # List to collect progress messages
            progress_messages = []
            
            # Create a callback wrapper that collects progress updates
            def progress_callback(message, level='info'):
                """Callback to collect progress messages."""
                progress_messages.append({
                    'message': message,
                    'level': level
                })
            
            # Execute the step with progress callback if enabled
            try:
                if enable_progress:
                    # Try to pass progress_callback to the step function
                    result = step_func(*args, progress_callback=progress_callback)
                else:
                    result = step_func(*args)
            except TypeError as e:
                # If the function doesn't accept progress_callback, try without it
                if 'progress_callback' in str(e):
                    result = step_func(*args)
                else:
                    raise
            
            # Emit all collected progress messages
            for prog in progress_messages:
                data = {
                    'progress': prog['message'],
                    'level': prog['level'],
                    'task_id': task_id
                }
                yield f"data: {json.dumps(data)}\n\n"
            
            # Send result
            if isinstance(result, (list, tuple)):
                if len(result) >= 3:
                    success = result[0]
                    output = result[1]
                    message = result[2]
                    command = result[3] if len(result) > 3 else None
                    stats = result[4] if len(result) > 4 else None
                    
                    data = {
                        'done': True,
                        'success': success,
                        'output': output,
                        'message': message,
                        'command': command,
                        'task_id': task_id
                    }
                    if stats:
                        data['stats'] = stats
                else:
                    data = {
                        'done': True,
                        'success': False,
                        'error': 'Invalid step result',
                        'task_id': task_id
                    }
            else:
                data = {
                    'done': True,
                    'success': False,
                    'error': 'Step function did not return tuple/list',
                    'task_id': task_id
                }
            
            yield f"data: {json.dumps(data)}\n\n"
            
        except Exception as e:
            logger.error(f"Pipeline step error: {str(e)}")
            data = {
                'done': True,
                'success': False,
                'error': str(e),
                'task_id': task_id
            }
            yield f"data: {json.dumps(data)}\n\n"
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )
