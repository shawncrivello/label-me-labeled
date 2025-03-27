"""Progress indicator utilities for long-running operations."""

import sys
import time
import threading
from typing import Callable, Optional, Any


class ProgressIndicator:
    """
    A class that provides progress indicators for long-running operations.
    
    This class supports several styles of progress indicators, including:
    - Progress bar
    - Spinner
    - Percentage indicator
    - Custom formats
    
    Attributes:
        total: Total number of steps
        width: Width of the progress bar
        style: Style of the progress indicator
        description: Description text
        bar_char: Character to use for the progress bar
        completed_char: Character to use for completed progress
        remaining_char: Character to use for remaining progress
        spinner_chars: Characters to use for spinner animation
        _current: Current progress value
        _start_time: Time when the progress started
        _running: Whether the progress indicator is running
        _thread: Thread for async progress display
    """

    # Spinner character sets
    SPINNERS = {
        'classic': ['-', '\\', '|', '/'],
        'dots': ['.', '..', '...', '....'],
        'braille': ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'],
        'arrows': ['←', '↖', '↑', '↗', '→', '↘', '↓', '↙'],
        'bouncing': ['[    ]', '[=   ]', '[==  ]', '[=== ]', '[ ===]', '[  ==]', '[   =]', '[    ]', 
                    '[   =]', '[  ==]', '[ ===]', '[=== ]', '[==  ]', '[=   ]'],
    }

    def __init__(
        self, 
        total: int = 100, 
        width: int = 40, 
        style: str = 'bar', 
        description: str = 'Progress',
        bar_char: str = '█',
        completed_char: str = '█',
        remaining_char: str = '░',
        spinner_style: str = 'braille'
    ):
        """
        Initialize the progress indicator.
        
        Args:
            total: Total number of steps
            width: Width of the progress bar
            style: Style of the progress indicator ('bar', 'spinner', 'percent', 'simple')
            description: Description text
            bar_char: Character to use for the progress bar
            completed_char: Character to use for completed progress
            remaining_char: Character to use for remaining progress
            spinner_style: Style of spinner animation
        """
        self.total = max(1, total)  # Minimum of 1 to avoid division by zero
        self.width = width
        self.style = style
        self.description = description
        self.bar_char = bar_char
        self.completed_char = completed_char
        self.remaining_char = remaining_char
        self.spinner_chars = self.SPINNERS.get(spinner_style, self.SPINNERS['classic'])
        
        self._current = 0
        self._start_time = 0
        self._running = False
        self._thread = None
        self._last_update = 0
        self._spinner_idx = 0
        self._last_line_length = 0
        
        # Check if the output is a terminal
        self._is_terminal = sys.stdout.isatty()
        
        # Determine if colors are supported
        self._use_colors = self._is_terminal
    
    def _format_time(self, seconds: float) -> str:
        """
        Format seconds into a human-readable time string.
        
        Args:
            seconds: Number of seconds
            
        Returns:
            Formatted time string
        """
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds // 60
            seconds = seconds % 60
            return f"{int(minutes)}m {int(seconds)}s"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{int(hours)}h {int(minutes)}m"
    
    def _calculate_eta(self) -> str:
        """
        Calculate the estimated time remaining.
        
        Returns:
            ETA string
        """
        if self._current == 0:
            return "calculating..."
        
        elapsed = time.time() - self._start_time
        rate = self._current / elapsed if elapsed > 0 else 0
        remaining = (self.total - self._current) / rate if rate > 0 else 0
        
        return self._format_time(remaining)
    
    def _format_bar(self) -> str:
        """
        Format a progress bar.
        
        Returns:
            Formatted progress bar string
        """
        percent = min(100, int(self._current / self.total * 100))
        filled_width = int(self.width * self._current / self.total)
        
        # Create the progress bar
        bar = self.completed_char * filled_width + self.remaining_char * (self.width - filled_width)
        
        # Calculate speed and ETA
        elapsed = time.time() - self._start_time
        speed = self._current / elapsed if elapsed > 0 else 0
        eta = self._calculate_eta()
        
        # Format progress line
        return f"{self.description}: |{bar}| {percent}% ({self._current}/{self.total}) {speed:.1f} it/s ETA: {eta}"
    
    def _format_spinner(self) -> str:
        """
        Format a spinner indicator.
        
        Returns:
            Formatted spinner string
        """
        # Update spinner index
        self._spinner_idx = (self._spinner_idx + 1) % len(self.spinner_chars)
        spinner = self.spinner_chars[self._spinner_idx]
        
        # Calculate progress if possible
        if self.total > 0:
            percent = min(100, int(self._current / self.total * 100))
            return f"{self.description}: {spinner} {percent}% ({self._current}/{self.total})"
        else:
            return f"{self.description}: {spinner}"
    
    def _format_percent(self) -> str:
        """
        Format a percentage indicator.
        
        Returns:
            Formatted percentage string
        """
        percent = min(100, int(self._current / self.total * 100))
        return f"{self.description}: {percent}% ({self._current}/{self.total})"
    
    def _format_simple(self) -> str:
        """
        Format a simple indicator.
        
        Returns:
            Formatted simple string
        """
        return f"{self.description}: {self._current}/{self.total}"
    
    def _update_display(self) -> None:
        """Update the progress display."""
        # Throttle updates to avoid excessive screen refreshes
        current_time = time.time()
        if current_time - self._last_update < 0.1 and self._current < self.total:
            return
        
        self._last_update = current_time
        
        # Format the progress line based on style
        if self.style == 'bar':
            line = self._format_bar()
        elif self.style == 'spinner':
            line = self._format_spinner()
        elif self.style == 'percent':
            line = self._format_percent()
        elif self.style == 'simple':
            line = self._format_simple()
        else:
            line = self._format_bar()  # Default to bar
        
        # Clear previous line if in a terminal
        if self._is_terminal:
            # Calculate padding to clear the previous line
            padding = max(0, self._last_line_length - len(line))
            sys.stdout.write(f"\r{line}{' ' * padding}")
            sys.stdout.flush()
        else:
            # For non-terminal output, just print a new line
            if self._current == 0 or self._current == self.total:
                print(line)
        
        self._last_line_length = len(line)
    
    def start(self) -> None:
        """Start the progress indicator."""
        self._current = 0
        self._start_time = time.time()
        self._running = True
        self._update_display()
        
        # Start async display thread if using spinner
        if self.style == 'spinner':
            def _spin():
                while self._running:
                    self._update_display()
                    time.sleep(0.1)
            
            self._thread = threading.Thread(target=_spin)
            self._thread.daemon = True
            self._thread.start()
    
    def update(self, current: Optional[int] = None, advance: int = 1) -> None:
        """
        Update the progress indicator.
        
        Args:
            current: New current value (if None, advance by increment)
            advance: Amount to advance if current is None
        """
        if current is not None:
            self._current = min(current, self.total)
        else:
            self._current = min(self._current + advance, self.total)
        
        # Don't spin in the update method to avoid excessive updates
        if self.style != 'spinner':
            self._update_display()
    
    def finish(self) -> None:
        """Complete the progress and clean up."""
        self._current = self.total
        self._running = False
        
        # Final update
        self._update_display()
        
        # Add a newline if in terminal
        if self._is_terminal:
            print()
        
        # Wait for thread to finish if exists
        if self._thread and self._thread.is_alive():
            self._thread.join(0.2)
    
    def __enter__(self) -> 'ProgressIndicator':
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.finish()


class ProgressCallback:
    """
    A class that converts progress to a callback function.
    
    This is useful for providing progress updates through callback interfaces,
    like those used in batch operations.
    
    Attributes:
        progress: ProgressIndicator instance
        total: Total number of steps
        current: Current progress value
    """

    def __init__(self, progress: ProgressIndicator):
        """
        Initialize the progress callback.
        
        Args:
            progress: ProgressIndicator instance
        """
        self.progress = progress
        self.total = progress.total
        self.current = 0
    
    def __call__(self, current: int, total: int, message: Optional[str] = None) -> None:
        """
        Update progress when the callback is called.
        
        Args:
            current: Current progress value
            total: Total number of steps
            message: Optional message to display
        """
        # Update total if it changed
        if total != self.total:
            self.total = total
            self.progress.total = total
        
        # Update current value
        self.current = current
        
        # Update description if message is provided
        if message:
            self.progress.description = message
        
        # Update the progress indicator
        self.progress.update(current)


# Convenience function to create a progress bar for a task
def create_progress_bar(total: int, description: str = "Progress", style: str = "bar") -> ProgressIndicator:
    """
    Create a progress bar for a task.
    
    Args:
        total: Total number of steps
        description: Description of the task
        style: Style of progress indicator
        
    Returns:
        ProgressIndicator instance
    """
    return ProgressIndicator(
        total=total,
        description=description,
        style=style
    )


# Convenience function to get a progress callback
def get_progress_callback(description: str = "Progress", total: int = 100, style: str = "bar") -> Callable:
    """
    Get a callback function for progress updates.
    
    Args:
        description: Description of the task
        total: Total number of steps
        style: Style of progress indicator
        
    Returns:
        Callback function for progress updates
    """
    progress = ProgressIndicator(
        total=total,
        description=description,
        style=style
    )
    progress.start()
    
    callback = ProgressCallback(progress)
    
    # Add finish method to the callback
    callback.finish = progress.finish
    
    return callback