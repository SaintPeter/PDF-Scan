import os
import re
import sys
import glob

if len(sys.argv) == 2:
    search_path = sys.argv[1]
else:
    print("Invalid number of parameters, 1 required")
    print("Params: ")
    print(sys.argv)
    sys.exit(1)


for filename in glob.glob(os.path.join(search_path,"*.pdf")):
    result = re.compile("\d{2,6}").search(filename)
    if result:
        old_filename = os.path.basename(filename)

        new_filename = "Job_%06d_%s" % (int(result[0]), old_filename)
        print("Renamed: ", old_filename, "to", new_filename)
        new_filename = os.path.join(search_path, new_filename)
        os.rename(filename, new_filename)
    else:
        print("Skip: ", filename)