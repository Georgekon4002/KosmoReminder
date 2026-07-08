import subprocess
import sys
import os

def main():
    exe_path = os.path.join("dist", "KosmoReminder.exe")
    
    if not os.path.exists(exe_path):
        print(f"Error: Executable not found at {exe_path}")
        print("Please run build.bat first to generate the executable.")
        input("Press Enter to exit...")
        sys.exit(1)
        
    print("Starting KosmoReminder Dashboard...")
    dashboard = subprocess.Popen([exe_path])
    
    try:
        # Wait for the UI to close
        dashboard.wait()
    except KeyboardInterrupt:
        pass
    finally:
        print("Dashboard closed.")

if __name__ == "__main__":
    main()
