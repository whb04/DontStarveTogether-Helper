import os
import shutil
import subprocess
import threading
import argparse
from datetime import datetime
import yaml

# Load configuration from config.yaml
config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
with open(config_path, 'r') as config_file:
    config = yaml.safe_load(config_file)

# Assign configuration values to variables
log_dir = config['log_dir']
save_dir = config['save_dir']
migrate_dir = config['migrate_dir']
game_dir = config['game_dir']
steam_account = config['steam_account']
cluster_token = config['cluster_token']
adminlist = config['adminlist']

# Create log directory
os.makedirs(log_dir, exist_ok=True)

# Helper function to generate dedicated_server_mods_setup.lua based on modoverrides.lua
def generate_mods_setup(modoverrides_path, mods_setup_path):
    if not os.path.exists(modoverrides_path):
        print(f"Warning: {modoverrides_path} not found. Cannot generate mods setup file.")
        return

    mods_list = []
    with open(modoverrides_path, 'r') as modoverrides_file:
        for line in modoverrides_file:
            stripped_line = line.strip()
            if stripped_line.startswith('["workshop-'):
                # Extract workshop ID
                workshop_id = stripped_line.split('"')[1].replace("workshop-", "")
                mods_list.append(workshop_id)

    # Write the mods setup file
    with open(mods_setup_path, 'w') as mods_setup_file:
        for mod in mods_list:
            mods_setup_file.write(f'ServerModSetup("{mod}")\n')

    print(f"Generated mods setup file at {mods_setup_path}")

# Helper function to check if the save structure is correct
def check_save_structure(save_path):
    required_dirs = ["Master", "Caves"]
    required_files = ["cluster_token.txt"]
    warning_files = ["adminlist.txt"]
    
    missing_dirs = [d for d in required_dirs if not os.path.exists(os.path.join(save_path, d))]
    missing_files = [f for f in required_files if not os.path.exists(os.path.join(save_path, f))]
    warning_files_missing = [f for f in warning_files if not os.path.exists(os.path.join(save_path, f))]
    
    if missing_dirs or missing_files:
        print(f"Error: Missing required directories or files in the save folder: {', '.join(missing_dirs + missing_files)}")
        return False
    
    if warning_files_missing:
        print(f"Warning: Missing optional files in the save folder: {', '.join(warning_files_missing)}")
    
    return True

# Generate missing files in the save folder
def generate_missing_files(save_name):
    save_path = os.path.join(save_dir, save_name)
    cluster_token_path = os.path.join(save_path, "cluster_token.txt")
    adminlist_path = os.path.join(save_path, "adminlist.txt")

    # Generate cluster token file
    if not os.path.exists(cluster_token_path):
        with open(cluster_token_path, 'w') as cluster_token_file:
            cluster_token_file.write(cluster_token)
        print(f"Generated cluster token file at {cluster_token_path}")

    # Generate adminlist file
    if not os.path.exists(adminlist_path):
        with open(adminlist_path, 'w') as adminlist_file:
            for admin in adminlist:
                adminlist_file.write(f"{admin}\n")
        print(f"Generated adminlist file at {adminlist_path}")

# Helper function to generate a log file name with a timestamp and save name
def generate_log_filename(save_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(log_dir, exist_ok=True)
    return os.path.join(log_dir, f"{save_name}_{timestamp}.log")

# Function to migrate a save and generate the mods setup file
def migrate_save(save_name):
    save_src = os.path.join(migrate_dir, save_name)
    save_dst = os.path.join(save_dir, save_name)

    # Check if the source save directory exists and has the correct structure
    if os.path.exists(save_src):
        
        generate_missing_files(save_name)

        if not check_save_structure(save_src):
            print(f"Error: Save structure invalid in {save_src}. Migration aborted.")
            return

        if os.path.exists(save_dst):
            print(f"Warning: Save folder {save_dst} already exists. Deleting...")
            shutil.rmtree(save_dst)

        # Copy save folder
        print(f"Migrating save from {save_src} to {save_dst}...")
        shutil.copytree(save_src, save_dst, dirs_exist_ok=True)

        # Generate mods setup file based on modoverrides.lua
        modoverrides_path = os.path.join(save_dst, "Master", "modoverrides.lua")
        mods_setup_path = os.path.join(game_dir, "mods", "dedicated_server_mods_setup.lua")
        generate_mods_setup(modoverrides_path, mods_setup_path)
    else:
        print(f"Warning: Save folder {save_src} not found. Migration skipped.")

# Function to update the game and regenerate the mods setup file
def update_game(save_name):
    mods_dir = os.path.join(game_dir, "mods")
    mods_setup_file = os.path.join(mods_dir, "dedicated_server_mods_setup.lua")
    modoverrides_path = os.path.join(save_dir, save_name, "Master", "modoverrides.lua")
    bin_dir = os.path.join(game_dir, "bin64")

    # Step 1: Run the game update command
    steam_update_cmd = ["steamcmd", "+login", steam_account, "+app_update", "343050", "validate", "+quit"]

    print("Updating game...")
    subprocess.run(steam_update_cmd)
    print("Game update completed.")

    # Step 2: Regenerate the mods setup file after the game update
    generate_mods_setup(modoverrides_path, mods_setup_file)

    # Step 3: Change to the bin64 directory and run the mod update
    print("Updating server mods...")
    update_mods_cmd = [os.path.join(bin_dir, "dontstarve_dedicated_server_nullrenderer_x64"), "-cluster", save_name, "-only_update_server_mods"]

    # Ensure we are running the command in the bin64 directory
    subprocess.run(update_mods_cmd, cwd=bin_dir)
    print("Server mod update completed.")

# Function to log output of a process
def log_output(process, prefix, log_file, event):
    triggered = False
    with open(log_file, 'a') as log:
        for line in iter(process.stdout.readline, b''):
            decoded_line = line.decode('utf-8')
            log.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {prefix}: {decoded_line}")
            if not triggered and "Sim paused" in decoded_line:
                event.set()
                triggered = True
        process.stdout.close()

# Function to start the game
def start_game(save_name):
    cluster_name = save_name
    bin_dir = os.path.join(game_dir, "bin64")

    run_shared = [os.path.join(bin_dir, "dontstarve_dedicated_server_nullrenderer_x64"),
                  "-cluster", cluster_name, "-monitor_parent_process", str(os.getpid())]

    # Commands for Caves and Master
    caves_cmd = run_shared + ["-shard", "Caves"]
    master_cmd = run_shared + ["-shard", "Master"]

    # Log file path based on save name and timestamp
    log_file = generate_log_filename(save_name)

    # Open the log file and write the start time
    with open(log_file, 'a') as log:
        log.write(f"\n\n==== Game Start: {datetime.now()} ====\n")

    print(f"Starting server for {save_name}...")

    # Start both processes
    caves_process = subprocess.Popen(caves_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=bin_dir)
    master_process = subprocess.Popen(master_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=bin_dir)

    # Event to signal when "Sim paused" is detected
    event = threading.Event()

    # Start threads to capture output concurrently
    caves_thread = threading.Thread(target=log_output, args=(caves_process, "Caves", log_file, event))
    master_thread = threading.Thread(target=log_output, args=(master_process, "Master", log_file, event))

    caves_thread.start()
    master_thread.start()

    # Wait for "Sim paused" signal
    event.wait()

    print(f"Server started successfully, log saved in {log_file}. Type 'e' or 'exit' to terminate the server.")

    # Input loop to terminate the server
    while True:
        user_input = input()
        if user_input.lower() in ['e', 'exit']:
            print("Exiting...")
            caves_process.terminate()
            master_process.terminate()
            break
        else:
            print("Unkown command.")

    # Wait for both processes to finish
    caves_thread.join()
    master_thread.join()

    caves_process.wait()
    master_process.wait()

    print("Game End.")
    with open(log_file, 'a') as log:
        log.write(f"==== Game End: {datetime.now()} ====\n")

# Function to backup a save
def backup_save(save_name):
    save_path = os.path.join(save_dir, save_name)
    backup_dir = os.path.join(save_dir, "backups")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"{save_name}_{timestamp}")

    # Check if the save directory exists
    if not os.path.exists(save_path):
        print(f"Error: Save directory {save_path} does not exist. Backup aborted.")
        return

    # Create the backup directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)

    # Copy the save directory to the backup location
    try:
        shutil.copytree(save_path, backup_path)
        print(f"Backup created successfully at {backup_path}")
    except Exception as e:
        print(f"Error during backup: {e}")

# Function to check if necessary files exist in the save folder
def check_files(save_name):
    save_path = os.path.join(save_dir, save_name)
    if check_save_structure(save_path):
        print(f"All necessary files exist in the save folder: {save_path}")
    else:
        print(f"Some necessary files are missing in the save folder: {save_path}")

# Main function to parse command-line arguments
def main():
    parser = argparse.ArgumentParser(description="Server management tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Migrate save (short 'm')
    migrate_parser = subparsers.add_parser("m", help="Migrate save")
    migrate_parser.add_argument("save_name", type=str, help="Name of the save")

    # Update (short 'u')
    update_parser = subparsers.add_parser("u", help="Update the game")
    update_parser.add_argument("save_name", type=str, help="Name of the save")

    # Start (short 's')
    start_parser = subparsers.add_parser("s", help="Start the game")
    start_parser.add_argument("save_name", type=str, help="Name of the save")

    # Update and start (short 'us')
    us_parser = subparsers.add_parser("us", help="Update and start the game")
    us_parser.add_argument("save_name", type=str, help="Name of the save")

    # Backup save (short 'b')
    backup_parser = subparsers.add_parser("b", help="Backup save")
    backup_parser.add_argument("save_name", type=str, help="Name of the save")

    # Check for files (short 'c')
    check_parser = subparsers.add_parser("c", help="Check if necessary files exist")
    check_parser.add_argument("save_name", type=str, help="Name of the save")

    # Parse arguments
    args = parser.parse_args()

    # Execute corresponding functionality based on command
    if args.command == "m":
        migrate_save(args.save_name)
    elif args.command == "u":
        update_game(args.save_name)
    elif args.command == "s":
        start_game(args.save_name)
    elif args.command == "us":
        update_game(args.save_name)
        start_game(args.save_name)
    elif args.command == "b":
        backup_save(args.save_name)
    elif args.command == "c":
        check_files(args.save_name)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
