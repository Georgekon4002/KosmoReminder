import subprocess
import sys
import os

def main():
    print("Starting KosmoSMS Backend Services...")
    
    # Start the callback receiver and reminder service
    receiver = subprocess.Popen([sys.executable, "src/callback_receiver.py"])
    reminder = subprocess.Popen([sys.executable, "src/reminder_service.py"])
    
    exe_path = os.path.join("dist", "KosmoSMS_Dashboard.exe")
    
    if not os.path.exists(exe_path):
        print(f"Error: Executable not found at {exe_path}")
        print("Please run build.bat first to generate the executable.")
        # Cleanup
        receiver.terminate()
        reminder.terminate()
        input("Press Enter to exit...")
        sys.exit(1)
        
    print("Starting KosmoSMS Dashboard...")
    dashboard = subprocess.Popen([exe_path])
    
    try:
        # Wait for the UI to close
        dashboard.wait()
    except KeyboardInterrupt:
        pass
    finally:
        print("Dashboard closed. Stopping backend services...")
        receiver.terminate()
        reminder.terminate()
        print("All services stopped.")

if __name__ == "__main__":
    main()
