"""Confirmation utilities for user interaction."""

import sys
from typing import Optional, List

from legal_drive_labels_manager.utils.config import get_config


def confirm_action(
    prompt: str, 
    default: bool = False,
    destructive: bool = True
) -> bool:
    """
    Ask for user confirmation before performing an action.
    
    Args:
        prompt: Confirmation prompt to display
        default: Default action if user just presses Enter
        destructive: Whether this is a destructive action (can be overridden by config)
        
    Returns:
        True if confirmed, False otherwise
    """
    # Check if confirmation is disabled in config
    config = get_config()
    if destructive and not config.get("ui", "confirm_destructive", True):
        return True
    
    # Add appropriate hint
    yes_no = "[Y/n]" if default else "[y/N]"
    
    # Format the prompt
    if not prompt.endswith(" "):
        prompt += " "
    
    full_prompt = f"{prompt}{yes_no}: "
    
    # Loop until valid input
    while True:
        try:
            response = input(full_prompt).strip().lower()
            
            # Handle empty response
            if not response:
                return default
            
            # Handle yes/no responses
            if response in ["y", "yes"]:
                return True
            elif response in ["n", "no"]:
                return False
            else:
                # Invalid response, ask again
                print("Please answer 'y/yes' or 'n/no'.")
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print("\nOperation cancelled.")
            return False


def prompt_with_default(prompt: str, default: Optional[str] = None) -> str:
    """
    Prompt for input with an optional default value.
    
    Args:
        prompt: Prompt text
        default: Default value if user just presses Enter
        
    Returns:
        User input or default value
    """
    # Add default value to prompt if provided
    if default is not None:
        if not prompt.endswith(" "):
            prompt += " "
        
        full_prompt = f"{prompt}[{default}]: "
    else:
        full_prompt = prompt
        
        if not full_prompt.endswith(" "):
            full_prompt += ": "
    
    try:
        response = input(full_prompt).strip()
        
        # Return default if response is empty
        if not response and default is not None:
            return default
        
        return response
    except KeyboardInterrupt:
        # Handle Ctrl+C
        print("\nOperation cancelled.")
        sys.exit(1)


def prompt_for_choice(
    prompt: str, 
    choices: List[str], 
    default: Optional[int] = None
) -> str:
    """
    Prompt user to select from a list of choices.
    
    Args:
        prompt: Prompt text
        choices: List of choices
        default: Default choice index
        
    Returns:
        Selected choice
    """
    if not choices:
        raise ValueError("No choices provided")
    
    # Print prompt
    print(f"{prompt}")
    
    # Print numbered choices
    for i, choice in enumerate(choices):
        default_marker = " (default)" if i == default else ""
        print(f"{i+1}. {choice}{default_marker}")
    
    # Default choice text
    default_text = f" [{default+1}]" if default is not None else ""
    
    # Loop until valid selection
    while True:
        try:
            response = input(f"Enter selection{default_text}: ").strip()
            
            # Handle empty response
            if not response and default is not None:
                return choices[default]
            
            # Handle numeric response
            try:
                index = int(response) - 1
                if 0 <= index < len(choices):
                    return choices[index]
                else:
                    print(f"Please enter a number between 1 and {len(choices)}.")
            except ValueError:
                # Check if response matches a choice
                matches = [choice for choice in choices if choice.lower() == response.lower()]
                if matches:
                    return matches[0]
                else:
                    print(f"Please enter a number between 1 and {len(choices)}.")
        except KeyboardInterrupt:
            # Handle Ctrl+C
            print("\nOperation cancelled.")
            sys.exit(1)