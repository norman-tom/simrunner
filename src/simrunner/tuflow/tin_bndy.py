import os
import sys
import subprocess

UTILITY = "C:\\tuflow\\utilities\\12da_to_from_gis\\12da_to_from_gis.exe"
TIN_BNDY = ".\\model\\tin\\basin_04_bndy.12da"

# Check that the TIN_BNDY is in ANSII format, and convert if not
def is_ansi(file_path):
    try:
        with open(file_path, 'rb') as f:
            if f.read()[0] == 0xb:
                return True
            return False
    except UnicodeDecodeError:
        return False
    
def main():
    # Check if the utility exists
    if not os.path.exists(UTILITY):
        print(f"Error: Utility not found: {UTILITY}")
        sys.exit(1)

    # Check that the TIN boundary file exists
    if not os.path.exists(TIN_BNDY):
        print(f"Error: TIN boundary file not found: {TIN_BNDY}")
        sys.exit(1)
        
    if not is_ansi(TIN_BNDY):
        # Convert the file to ANSI
        with open(TIN_BNDY, 'r', encoding='UTF-16') as f:
            data = f.read()
        with open(TIN_BNDY, 'w', encoding='mbcs') as f:
            f.write(data)
        print(f"Converted TIN boundary file to ANSI format: {TIN_BNDY}")

    # Resolve full path of the TIN_BNDY file
    path = os.path.abspath(TIN_BNDY)

    # Utility arguments
    args = f'"{UTILITY}" -b -shp "{path}"'
    print(f"Executing {args}")

    # Run the utility using subprocess
    subprocess.run(args)

if __name__ == "__main__":  
    main()