"""
results.py

Basic interface to display results in a browser.

"""
from urllib.parse import quote_plus
from platform import system
import webbrowser


def show_files_for_selection(file_list: list[str] | None) -> None:
    """
    Takes the list of files provided, opens the default browser and displays them with associated links.
    Assumes that the internal server is running.

    Args:
        file_list (list[str] | None): If not None, contains a list of files to display.
    """
    if file_list is not None:
        filenames: str = "%%".join(file_list)
        names = quote_plus(filenames)
        url: str = f"http://localhost:5726/api/menu/{names}"
        if system() == "Windows":
            edge_path = (
                "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe %s"
            )
            # chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
            webbrowser.get(edge_path).open(url)
        else:
            webbrowser.open(url)


if __name__ == "__main__":
    print("testing webbrowser")
    edge_path = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe %s"
    chrome_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
    # webbrowser.register("edge", None, webbrowser.BackgroundBrowser(edge_path))
    # webbrowser.register("chrome", None, webbrowser.BackgroundBrowser(chrome_path))
    # webbrowser.get("edge").open("www.google.com")
    webbrowser.get(edge_path).open("https://www.mcgill.ca")
