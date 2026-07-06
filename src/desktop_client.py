import sys
import webview

def main():
    """
    Start a thin desktop client for the KosmoSMS Dashboard.
    
    By default it points to http://localhost:5000/
    You can override this by passing the URL as a command line argument.
    """
    target_url = "http://localhost:5000/"
    
    if len(sys.argv) > 1:
        target_url = sys.argv[1]

    # Create the native desktop window
    webview.create_window(
        title="KosmoSMS Dashboard",
        url=target_url,
        width=1280,
        height=800,
        resizable=True,
        min_size=(800, 600),
        maximized=True
    )
    
    # Launch the application
    webview.start()

if __name__ == '__main__':
    main()
