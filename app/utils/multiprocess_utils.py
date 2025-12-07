"""
Utilities for running functions in a separate process.
"""
import multiprocessing
from app.utils.logger import get_app_logger

logger = get_app_logger()

def _wrapper(queue, target, *args, **kwargs):
    """
    A wrapper function to execute a target function and put the result in a queue.
    This function is executed in a separate process.
    """
    try:
        result = target(*args, **kwargs)
        queue.put(result)
    except Exception as e:
        logger.error(f"Error in subprocess: {e}")
        queue.put(e)

def run_in_process(target, *args, **kwargs):
    """
    Runs a target function in a separate process to isolate it.

    Args:
        target: The function to execute.
        *args: Positional arguments for the target function.
        **kwargs: Keyword arguments for the target function.

    Returns:
        The result of the target function, or raises the exception that occurred in the subprocess.
    """
    # Use a manager queue to share data between processes
    manager = multiprocessing.Manager()
    queue = manager.Queue()

    # Create and start the process
    process = multiprocessing.Process(target=_wrapper, args=(queue, target, *args), kwargs=kwargs)
    process.start()
    process.join()  # Wait for the process to complete

    # Get the result from the queue
    result = queue.get()

    if isinstance(result, Exception):
        raise result

    return result
