import os
import sys
import shutil
import threading
import time
import psutil
import hashlib
import argparse
from tqdm import tqdm
from colorama import Fore, Style, init

# Initialize Colorama for cross-platform colored text
init(autoreset=True)

# --- Global state for communication between threads ---
copy_error = None
currently_processed_file = "Initializing..."
status_message = "" # New global for status updates

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

def _copy_file_with_retry(src_file: str, dest_file: str, retries: int):
    """Helper function to handle the copy and retry logic for a single file."""
    global copy_error, currently_processed_file, status_message
    
    for attempt in range(retries + 1):
        try:
            shutil.copy2(src_file, dest_file)
            status_message = "" # Clear status on success
            return 
        except Exception as e:
            if attempt < retries:
                retry_delay = 3
                # --- MODIFIED: Set global status message instead of writing to console ---
                status_message = (f"{Fore.YELLOW}Error on '{currently_processed_file}': {e}. "
                                  f"Retrying... (Attempt {attempt + 1}/{retries}){Style.RESET_ALL}")
                time.sleep(retry_delay)
            else:
                status_message = "" # Clear status on final failure
                copy_error = (e, currently_processed_file)
                raise
    # After a successful retry, clear the message
    status_message = ""


def checksum_copy_worker(source: str, destination: str, retries: int, pbar: tqdm):
    """
    Copies files and folders, performing checksum verification and retries.
    """
    global copy_error, currently_processed_file, status_message
    try:
        if os.path.isfile(source):
            currently_processed_file = os.path.basename(source)
            dest_file = os.path.join(destination, os.path.basename(source))
            os.makedirs(destination, exist_ok=True)
            if not (os.path.exists(dest_file) and get_checksum(source) == get_checksum(dest_file)):
                _copy_file_with_retry(source, dest_file, retries)
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
                    _copy_file_with_retry(src_file, dest_file, retries)
                pbar.update(os.path.getsize(src_file))
    except Exception:
        return
    finally:
        currently_processed_file = "Finalizing..."
        status_message = ""

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
    
    parser = argparse.ArgumentParser(
        description="Advanced Python File Copy Utility with progress, stats, and retries.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"Usage examples:\n"
               f"  python {sys.argv[0]} \"C:\\source_folder\" \"D:\\destination_folder\"\n"
               f"  python {sys.argv[0]} \"./my file.zip\" \"./backup\" --retry 3"
    )
    parser.add_argument("source", help="The source file or folder path.")
    parser.add_argument("destination", help="The destination folder path.")
    parser.add_argument("--retry", type=int, default=0, help="Number of times to retry a failed file copy.\nDefault is 0 (one attempt, no retries).")
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
        
    args = parser.parse_args()
    
    source_path = args.source
    dest_path = args.destination

    def print_ui_frame(mode_str=""):
        clear_screen()
        print(f"{Style.BRIGHT}\n--- Advanced Python File Copy Utility ---{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}{mode_str}{Style.RESET_ALL}\n")
        print(f"{Style.BRIGHT}Source:      {Fore.CYAN}{source_path}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}Destination: {Fore.CYAN}{target_dest_path}{Style.RESET_ALL}")
        print(f"{Style.BRIGHT}Retries:     {Fore.YELLOW}{args.retry}{Style.RESET_ALL}\n")

    if not os.path.exists(source_path): print(f"{Fore.RED}Error: Source path does not exist: {source_path}"); return

    target_dest_path = os.path.join(dest_path, os.path.basename(source_path)) if os.path.isdir(source_path) else dest_path
    
    print_ui_frame("Preparing...")
    input("Press Enter to begin the transfer...")
    
    print_ui_frame("Calculating...")
    total_size = get_total_size(source_path)

    if total_size == 0: print(f"{Fore.YELLOW}Warning: Source is empty. Nothing to copy."); return
    
    pbar = tqdm(total=total_size, unit='B', unit_scale=True, colour='green', bar_format="{l_bar}{bar:50}{r_bar}", leave=True)
    
    copy_thread = threading.Thread(target=checksum_copy_worker, args=(source_path, target_dest_path, args.retry, pbar))
    copy_thread.daemon = True
    
    start_time = time.time()
    copy_thread.start()
    
    last_net_io = psutil.net_io_counters()
    last_check_time = time.time()
    last_term_size = shutil.get_terminal_size()
    
    try:
        while copy_thread.is_alive():
            current_term_size = shutil.get_terminal_size()
            if current_term_size != last_term_size:
                print_ui_frame("Transferring...")
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
            
            file_info = f"File: {currently_processed_file[:30]:<30}"
            stats_line = (f"{Fore.CYAN}CPU: {cpu_percent:>5.1f}%{Style.RESET_ALL} | "
                          f"{Fore.MAGENTA}RAM: {ram_percent:>5.1f}%{Style.RESET_ALL} | "
                          f"{Fore.GREEN}Up: {format_speed(upload_speed)}{Style.RESET_ALL} | "
                          f"{Fore.YELLOW}Down: {format_speed(download_speed)}{Style.RESET_ALL} | "
                          f"{Style.DIM}{file_info}{Style.RESET_ALL}")
            
            # --- MODIFIED: Manage a 3-line display (bar, stats, status) ---
            sys.stdout.write(f'\r{pbar}\n\x1b[2K{stats_line}\n\x1b[2K{status_message}\r')
            sys.stdout.flush()
            sys.stdout.write('\x1b[2A') # Move cursor up two lines
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n\n") # Move cursor below all UI elements
        print(f"{Fore.YELLOW}{Style.BRIGHT}✖ Operation cancelled by user.{Style.RESET_ALL}")
        sys.stdout.write('\x1b[?25h'); sys.stdout.flush()
        sys.exit(0)

    # --- FINALIZATION ---
    end_time = time.time()
    total_duration = end_time - start_time
    formatted_duration = format_duration(total_duration)

    if pbar.n < total_size: pbar.update(total_size - pbar.n)
    pbar.close()

    final_stats = (f"{Fore.CYAN}CPU: {psutil.cpu_percent():>5.1f}%{Style.RESET_ALL} | "
                   f"{Fore.MAGENTA}RAM: {psutil.virtual_memory().percent:>5.1f}%{Style.RESET_ALL} | "
                   f"{Fore.GREEN}Up: {format_speed(0)}{Style.RESET_ALL} | "
                   f"{Fore.YELLOW}Down: {format_speed(0)}{Style.RESET_ALL} | "
                   f"{Style.DIM}File: {'Complete':<30}{Style.RESET_ALL}")

    sys.stdout.write(f'\r\x1b[2K{final_stats}\n\x1b[2K\n') # Overwrite stats, clear status line
    sys.stdout.flush()

    if copy_error:
        error_exception, error_file = copy_error
        print(f"\n{Fore.RED}{Style.BRIGHT}An error occurred while processing file: {Fore.YELLOW}{error_file}{Style.RESET_ALL}")
        print(f"{Fore.RED}Error details: {error_exception}")
        print(f"\n{Fore.YELLOW}The operation was stopped. On the next run, copied files will be skipped automatically.")
    else:
        print(f"{Fore.BLUE}{Style.BRIGHT}✔ Transfer complete!{Style.RESET_ALL}")
        print(f"Total time elapsed: {Fore.YELLOW}{Style.BRIGHT}{formatted_duration}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
    sys.stdout.write('\x1b[?25h'); sys.stdout.flush()
    input("\nPress Enter to exit.")

