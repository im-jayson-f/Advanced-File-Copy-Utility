import os
import sys
import shutil
import threading
import time
import psutil
import hashlib
from tqdm import tqdm
from colorama import Fore, Style, init

# Initialize Colorama for cross-platform colored text
init(autoreset=True)

# --- Global state for communication between threads ---
copy_error = None
currently_processed_file = "Initializing..."

def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

def get_checksum(file_path: str) -> str | None:
    """Calculates the MD5 checksum of a file, returning None if the file is inaccessible."""
    hash_md5 = hashlib.md5()
    buffer_size = 65536
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(buffer_size), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except (IOError, OSError):
        return None

def get_total_size(path: str) -> int:
    """Recursively calculates the total size of a file or a directory."""
    if os.path.isfile(path): return os.path.getsize(path)
    total_size = 0
    try:
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.exists(fp) and not os.path.islink(fp):
                    total_size += os.path.getsize(fp)
    except OSError as e:
        tqdm.write(f"{Fore.RED}Error calculating size for {path}: {e}")
    return total_size

def checksum_copy_worker(source: str, destination: str, pbar: tqdm):
    """
    Copies files and folders, performing checksum verification. Updates the progress bar.
    Communicates the current file being processed via a global variable.
    """
    global copy_error, currently_processed_file
    try:
        if os.path.isfile(source):
            currently_processed_file = os.path.basename(source)
            dest_file = os.path.join(destination, os.path.basename(source))
            os.makedirs(destination, exist_ok=True)
            if not (os.path.exists(dest_file) and get_checksum(source) == get_checksum(dest_file)):
                shutil.copy2(source, dest_file)
            pbar.update(os.path.getsize(source))
            return

        for dirpath, _, filenames in os.walk(source):
            relative_dir = os.path.relpath(dirpath, source)
            dest_dir = os.path.join(destination, relative_dir)
            os.makedirs(dest_dir, exist_ok=True)
            for filename in filenames:
                currently_processed_file = filename
                src_file = os.path.join(dirpath, filename)
                dest_file = os.path.join(dest_dir, filename)
                if not (os.path.exists(dest_file) and get_checksum(src_file) == get_checksum(dest_file)):
                    shutil.copy2(src_file, dest_file)
                pbar.update(os.path.getsize(src_file))
    except Exception as e:
        copy_error = e
    finally:
        currently_processed_file = "Finalizing..."

def get_paths(mode_ref: dict):
    """Parses command-line arguments or prompts the user for paths."""
    source_path, dest_path = "", ""
    if len(sys.argv) >= 3:
        mode_ref['name'] = "Running in Command-Line Mode."
        source_path, dest_path = sys.argv[1], sys.argv[2]
    elif len(sys.argv) == 2:
        mode_ref['name'] = "Running in Drag-and-Drop Mode."
        source_path = sys.argv[1]
        print(f"Source Path Provided: {Fore.CYAN}{source_path}")
        dest_path = input(f"Enter the {Fore.YELLOW}DESTINATION{Style.RESET_ALL} folder path: ")
    else:
        mode_ref['name'] = "Running in Interactive Mode."
        source_path = input(f"Enter the {Fore.YELLOW}SOURCE{Style.RESET_ALL} file or folder path: ")
        dest_path = input(f"Enter the {Fore.YELLOW}DESTINATION{Style.RESET_ALL} folder path: ")
    return source_path.strip('"'), dest_path.strip('"')

def format_speed(speed_bytes_per_sec: float) -> str:
    """Formats speed in bytes/sec to a human-readable string."""
    if speed_bytes_per_sec > 1024 * 1024: return f"{speed_bytes_per_sec / (1024*1024):>6.2f} MB/s"
    elif speed_bytes_per_sec > 1024: return f"{speed_bytes_per_sec / 1024:>6.2f} KB/s"
    else: return f"{speed_bytes_per_sec:>6.2f} B/s"

def format_duration(seconds: float) -> str:
    """Formats a duration in seconds to a human-readable string."""
    secs = int(seconds)
    if secs < 60: return f"{secs} second(s)"
    minutes, secs = divmod(secs, 60)
    if minutes < 60: return f"{minutes} minute(s) and {secs} second(s)"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} hour(s), {minutes} minute(s), and {secs} second(s)"

def main():
    """Main function to orchestrate the copy process."""
    clear_screen()
    print(f"{Style.BRIGHT}\n--- Advanced Python File Copy Utility ---{Style.RESET_ALL}")
    
    mode_info = {'name': ''}
    source_path, dest_path = get_paths(mode_info)

    if not source_path or not dest_path: print(f"{Fore.RED}Error: Source and Destination paths are required."); return
    if not os.path.exists(source_path): print(f"{Fore.RED}Error: Source path does not exist: {source_path}"); return

    target_dest_path = os.path.join(dest_path, os.path.basename(source_path)) if os.path.isdir(source_path) else dest_path
    
    def print_ui_frame():
        clear_screen()
        print(f"{Style.BRIGHT}\n--- Advanced Python File Copy Utility ---{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{mode_info['name']}{Style.RESET_ALL}\n")
        print(f"{Style.BRIGHT}Source:      {Fore.CYAN}{source_path}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}Destination: {Fore.CYAN}{target_dest_path}{Style.RESET_ALL}\n")

    print_ui_frame()
    input("Press Enter to begin the transfer...")
    
    print_ui_frame() 
    
    sys.stdout.write("Calculating total size... ")
    sys.stdout.flush()
    total_size = get_total_size(source_path)
    sys.stdout.write(f"\r\x1b[2K")
    sys.stdout.flush()

    if total_size == 0: print(f"{Fore.YELLOW}Warning: Source is empty. Nothing to copy."); return
    
    pbar = tqdm(total=total_size, unit='B', unit_scale=True, colour='green', bar_format="{l_bar}{bar:50}{r_bar}", leave=True)
    
    copy_thread = threading.Thread(target=checksum_copy_worker, args=(source_path, target_dest_path, pbar))
    copy_thread.daemon = True # Allows main thread to exit and kill worker on Ctrl+C
    
    start_time = time.time()
    copy_thread.start()
    
    last_net_io = psutil.net_io_counters()
    last_check_time = time.time()
    last_term_size = shutil.get_terminal_size()
    
    try:
        while copy_thread.is_alive():
            current_term_size = shutil.get_terminal_size()
            if current_term_size != last_term_size:
                print_ui_frame()
                last_term_size = current_term_size

            cpu_percent = psutil.cpu_percent()
            ram_percent = psutil.virtual_memory().percent
            
            current_net_io = psutil.net_io_counters()
            current_time = time.time()
            elapsed_time = current_time - last_check_time
            
            upload_speed, download_speed = 0, 0
            if elapsed_time > 0:
                upload_speed = (current_net_io.bytes_sent - last_net_io.bytes_sent) / elapsed_time
                download_speed = (current_net_io.bytes_recv - last_net_io.bytes_recv) / elapsed_time
            last_net_io, last_check_time = current_net_io, current_time
            
            # --- FEATURE: Current file is now part of the stats line ---
            file_info = f"File: {currently_processed_file[:30]:<30}" # Truncate long filenames
            stats_line = (f"{Fore.CYAN}CPU: {cpu_percent:>5.1f}%{Style.RESET_ALL} | "
                          f"{Fore.MAGENTA}RAM: {ram_percent:>5.1f}%{Style.RESET_ALL} | "
                          f"{Fore.GREEN}Up: {format_speed(upload_speed)}{Style.RESET_ALL} | "
                          f"{Fore.YELLOW}Down: {format_speed(download_speed)}{Style.RESET_ALL} | "
                          f"{Style.DIM}{file_info}{Style.RESET_ALL}")
            
            sys.stdout.write(f'\r{pbar}\n\x1b[2K{stats_line}\r')
            sys.stdout.flush()
            sys.stdout.write('\x1b[1A')
            
            time.sleep(1)
    except KeyboardInterrupt:
        # --- FEATURE: Graceful exit on Ctrl+C ---
        print("\n\n") # Move cursor below the progress bar area
        print(f"{Fore.YELLOW}{Style.BRIGHT}✖ Operation cancelled by user.{Style.RESET_ALL}")
        # Make sure cursor is visible before exiting
        sys.stdout.write('\x1b[?25h')
        sys.stdout.flush()
        sys.exit(0)

    # --- FINALIZATION ---
    end_time = time.time()
    total_duration = end_time - start_time
    formatted_duration = format_duration(total_duration)

    pbar.update(total_size - pbar.n)
    pbar.close()
    copy_thread.join()

    final_stats = (f"{Fore.CYAN}CPU: {psutil.cpu_percent():>5.1f}%{Style.RESET_ALL} | "
                   f"{Fore.MAGENTA}RAM: {psutil.virtual_memory().percent:>5.1f}%{Style.RESET_ALL} | "
                   f"{Fore.GREEN}Up: {format_speed(0)}{Style.RESET_ALL} | "
                   f"{Fore.YELLOW}Down: {format_speed(0)}{Style.RESET_ALL} | "
                   f"{Style.DIM}File: {'Complete':<30}{Style.RESET_ALL}")
    
    sys.stdout.write(f'\r\x1b[2K{final_stats}\n')
    sys.stdout.flush()
    
    if copy_error:
        print(f"\n{Fore.RED}An error occurred during the copy process:\n{copy_error}")
    else:
        print()
        print(f"{Fore.BLUE}{Style.BRIGHT}✔ Transfer complete!{Style.RESET_ALL}")
        print(f"Total time elapsed: {Fore.YELLOW}{Style.BRIGHT}{formatted_duration}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
    # Ensure cursor is visible on normal exit too
    sys.stdout.write('\x1b[?25h')
    sys.stdout.flush()
    input("\nPress Enter to exit.")

