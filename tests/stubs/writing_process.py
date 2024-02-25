import time
import sys
import threading

def main():
    for _ in range(5):
        time.sleep(float(sys.argv[1]))
        print("I'm alive!", threading.get_ident())
    return 0

if __name__ == "__main__":
    main()