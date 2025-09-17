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
            parent_dir = os.path.dirname(dest_file)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            shutil.copy2(src_file, dest_file)
            status_message = "" # Clear status on success
            return 
        except Exception as e:
            if attempt < retries:
                retry_delay = 3
                error_str = str(e).replace('\n', ' ').replace('\r', '')
                status_message = (f"{Fore.YELLOW}Error on '{currently_processed_file}': {error_str}. "
                                  f"Retrying... (Attempt {attempt + 1}/{retries}){Style.RESET_ALL}")
                time.sleep(retry_delay)
            else:
                status_message = "" # Clear status on final failure
                copy_error = (e, currently_processed_file)
                raise
    status_message = ""

def checksum_copy_worker(source: str, destination: str, retries: int, pbar: tqdm):
    """
    Copies files and folders, performing checksum verification and retries (Full Sync).
    """
    global copy_error, currently_processed_file
    try:
        if os.path.isfile(source):
            currently_processed_file = os.path.basename(source)
            if not (os.path.exists(destination) and get_checksum(source) == get_checksum(destination)):
                _copy_file_with_retry(source, destination, retries)
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

def missing_files_copy_worker(files_to_copy: list, retries: int, pbar: tqdm):
    """
    Copies a pre-determined list of missing files.
    """
    global copy_error, currently_processed_file
    try:
        for src_file, dest_file in files_to_copy:
            currently_processed_file = os.path.basename(src_file)
            _copy_file_with_retry(src_file, dest_file, retries)
            pbar.update(os.path.getsize(src_file))
    except Exception:
        return
    finally:
        currently_processed_file = "Finalizing..."

def find_missing_files(source_path: str, dest_path: str) -> tuple[list, int]:
    """
    Scans for source files whose filenames do not exist anywhere in the destination path.
    """
    files_to_copy = []
    total_size = 0
    
    # --- FIX: Pre-scan destination to get all existing filenames ---
    dest_filenames = set()
    search_dir = ""
    
    if os.path.isdir(source_path):
        # If source is a directory, the search area is the destination directory
        search_dir = dest_path
    else:
        # If source is a file, the search area is the parent of the destination file path
        search_dir = os.path.dirname(dest_path)

    if os.path.isdir(search_dir):
        for _, _, filenames in os.walk(search_dir):
            for filename in filenames:
                dest_filenames.add(filename)

    # --- Now, check source against the collected destination filenames ---
    if os.path.isdir(source_path):
        for dirpath, _, filenames in os.walk(source_path):
            for filename in filenames:
                # Check if the filename itself is missing from the destination tree
                if filename not in dest_filenames:
                    src_file = os.path.join(dirpath, filename)
                    relative_path = os.path.relpath(src_file, source_path)
                    dst_file = os.path.join(dest_path, relative_path)
                    
                    files_to_copy.append((src_file, dst_file))
                    total_size += os.path.getsize(src_file)
    else: # It's a single file
        source_filename = os.path.basename(source_path)
        if source_filename not in dest_filenames:
            files_to_copy.append((source_path, dest_path))
            total_size += os.path.getsize(source_path)

    return files_to_copy, total_size

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

def run_transfer_monitoring(copy_thread: threading.Thread, pbar: tqdm, ui_frame_printer, mode_str: str):
    """Monitors a running copy thread, displaying stats and handling UI redraws."""
    start_time = time.time()
    copy_thread.daemon = True
    copy_thread.start()
    
    last_net_io = psutil.net_io_counters()
    last_check_time = time.time()
    last_term_size = shutil.get_terminal_size()
    
    try:
        while copy_thread.is_alive():
            current_term_size = shutil.get_terminal_size()
            if current_term_size != last_term_size:
                ui_frame_printer(mode_str)
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
            
            sys.stdout.write(f'\r{pbar}\n\x1b[2K{stats_line}\n\x1b[2K{status_message}\r')
            sys.stdout.flush()
            sys.stdout.write('\x1b[2A')
            
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n\n")
        print(f"{Fore.YELLOW}{Style.BRIGHT}✖ Operation cancelled by user.{Style.RESET_ALL}")
        sys.stdout.write('\x1b[?25h'); sys.stdout.flush()
        sys.exit(0)

    end_time = time.time()
    
    if pbar.n < pbar.total: pbar.update(pbar.total - pbar.n)
    pbar.close()
    copy_thread.join()
    
    return end_time - start_time

def main():
    """Main function to orchestrate the copy process."""
    clear_screen()
    
    parser = argparse.ArgumentParser(
        description="Advanced Python File Copy Utility with progress, stats, and retries.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=f"Usage examples:\n"
               f"  python {sys.argv[0]} \"C:\\source_folder\" \"D:\\destination_folder\"\n"
               f"  python {sys.argv[0]} \"./my file.zip\" \"./backup\" --retry 3\n"
               f"  python {sys.argv[0]} \"./source\" \"./dest\" --list-missing\n"
               f"  python {sys.argv[0]} \"./source\" \"./dest\" --list-missing copy-all"
    )
    parser.add_argument("source", help="The source file or folder path.")
    parser.add_argument("destination", help="The destination folder path.")
    parser.add_argument("--retry", type=int, default=0, help="Number of times to retry a failed file copy.\nDefault is 0 (one attempt, no retries).")
    parser.add_argument("--list-missing", nargs='?', const='display', default=None,
                        help="Displays missing files. Use '--list-missing copy-all' to copy just the missing files.")
    
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
        if not args.list_missing:
            print(f"{Style.BRIGHT}Retries:     {Fore.YELLOW}{args.retry}{Style.RESET_ALL}\n")

    if not os.path.exists(source_path): print(f"{Fore.RED}Error: Source path does not exist: {source_path}"); return

    if os.path.isdir(source_path):
        target_dest_path = dest_path
    else:
        if os.path.isdir(dest_path):
            target_dest_path = os.path.join(dest_path, os.path.basename(source_path))
        else:
            target_dest_path = dest_path
    
    if args.list_missing:
        mode = "Dry Run: Listing Missing Files" if args.list_missing == 'display' else "Copying Missing Files"
        print_ui_frame(mode)
        
        files_to_copy, total_missing_size = find_missing_files(source_path, target_dest_path)
        
        if not files_to_copy:
            print(f"\n{Fore.GREEN}✔ No missing files found.{Style.RESET_ALL}")
            sys.exit(0)

        print(f"\n{Fore.YELLOW}Found {len(files_to_copy)} missing file(s) ({tqdm.format_sizeof(total_missing_size, 'B')}):{Style.RESET_ALL}")
        for src, _ in sorted(files_to_copy):
            if os.path.isdir(source_path):
                 print(f" - {os.path.relpath(src, source_path)}")
            else:
                 print(f" - {os.path.basename(src)}")


        if args.list_missing == 'copy-all':
            input("\nPress Enter to begin copying these files...")
            print_ui_frame("Copying Missing Files...")
            
            pbar = tqdm(total=total_missing_size, unit='B', unit_scale=True, colour='green', bar_format="{l_bar}{bar:50}{r_bar}", leave=True)
            copy_thread = threading.Thread(target=missing_files_copy_worker, args=(files_to_copy, args.retry, pbar))
            total_duration = run_transfer_monitoring(copy_thread, pbar, print_ui_frame, "Copying Missing Files...")
        else:
            sys.exit(0)
    else:
        # --- Normal Full Sync Operation ---
        print_ui_frame("Preparing for Full Sync...")
        input("Press Enter to begin the transfer...")
        print_ui_frame("Calculating Total Size...")
        total_size = get_total_size(source_path)

        if total_size == 0: print(f"{Fore.YELLOW}Warning: Source is empty. Nothing to copy."); return
        
        pbar = tqdm(total=total_size, unit='B', unit_scale=True, colour='green', bar_format="{l_bar}{bar:50}{r_bar}", leave=True)
        copy_thread = threading.Thread(target=checksum_copy_worker, args=(source_path, target_dest_path, args.retry, pbar))
        total_duration = run_transfer_monitoring(copy_thread, pbar, print_ui_frame, "Performing Full Sync...")

    # --- FINALIZATION for both modes ---
    formatted_duration = format_duration(total_duration)

    final_stats = (f"{Fore.CYAN}CPU: {psutil.cpu_percent():>5.1f}%{Style.RESET_ALL} | "
                   f"{Fore.MAGENTA}RAM: {psutil.virtual_memory().percent:>5.1f}%{Style.RESET_ALL} | "
                   f"{Fore.GREEN}Up: {format_speed(0)}{Style.RESET_ALL} | "
                   f"{Fore.YELLOW}Down: {format_speed(0)}{Style.RESET_ALL} | "
                   f"{Style.DIM}File: {'Complete':<30}{Style.RESET_ALL}")

    sys.stdout.write(f'\r\x1b[2K{final_stats}\n\x1b[2K\n')
    sys.stdout.flush()

    if copy_error:
        error_exception, error_file = copy_error
        print(f"\n{Fore.RED}{Style.BRIGHT}An error occurred while processing file: {Fore.YELLOW}{error_file}{Style.RESET_ALL}")
        print(f"{Fore.RED}Error details: {error_exception}")
        print(f"\n{Fore.YELLOW}The operation was stopped. On the next run, copied files will be skipped automatically.")
    else:
        print(f"{Fore.BLUE}{Style.BRIGHT}✔ Operation complete!{Style.RESET_ALL}")
        print(f"Total time elapsed: {Fore.YELLOW}{Style.BRIGHT}{formatted_duration}{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
    sys.stdout.write('\x1b[?25h'); sys.stdout.flush()
    input("\nPress Enter to exit.")

