from fitz import open as fopen # PyMuPDF
from pytesseract import image_to_data, Output
from PIL import Image
from io import BytesIO
from csv import writer
from numpy import array, nan
from re import match, search
from tkinter import Tk
from tkinter.filedialog import askopenfilename
from os.path import exists


Tk().withdraw()

pdf_path = askopenfilename(
    title="Select PDF",
    filetypes=[("PDF files", "*.pdf")]
)

# Open PDF
file_name = pdf_path[:-4]
pdf = fopen(file_name + ".pdf")

file_path = file_name + ".csv"
counter = 0
while exists(file_path):
    counter += 1
    file_path = f"{file_name}({counter}).csv"

if counter > 0:
    file_path = file_name + f"({counter}).csv"

prev_line = []
check_line = []

with open(file_path, "w", newline="", encoding="utf-8") as f:
    writer = writer(f)

    for page_num in range(len(pdf)):
        print("page:", page_num+1)
        page = pdf[page_num]

        # Render page to image
        pix = page.get_pixmap(dpi=600)

        # Convert to PIL Image
        img_data = pix.tobytes("png")
        image = Image.open(BytesIO(img_data))

        img = array(image)
        height, width = img.shape[:2]
        amount_col = img[
                            0:int(height*0.95),          # all rows
                            int(width*0.80):width   # rightmost 20%
                        ]

        # OCR
        amount_text = image_to_data(amount_col, config="--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.,-", output_type=Output.DATAFRAME)
        amount_text["nums"] = amount_text["text"]
        text = image_to_data(image, config='--psm 6', output_type=Output.DATAFRAME)
        
        text = text.dropna(subset= ["text"])
        amount_text = amount_text.dropna(subset= ["text"])
        #lines = text.groupby("line_num").agg({"text": lambda x: " ".join(x), "top": lambda x: x.quantile(0.75)})

        # Remove bad rows
        text = text.dropna(subset=["text"])
        amount_text = amount_text.replace(r'^\s*$', nan, regex=True).dropna(subset=["text"])

        text = text[text["text"].str.strip() != ""]

        # Create approximate row grouping from y-coordinate
        LINE_TOLERANCE = text["height"].median()*1.6

        text["row_group"] = round(text["top"] / LINE_TOLERANCE) * LINE_TOLERANCE #round(text["top"] / text["height"]) * text["height"]

        # Sort top-to-bottom, then left-to-right
        text = text.sort_values(["row_group", "left"])

        # Rebuild lines
        lines = text.groupby("row_group").agg({"text": lambda x: " ".join(x), "top": lambda x: x.quantile(0.75)})

        results = []

        for _, main_row in lines.iterrows():

            main_y = main_row["top"]

            # Find closest amount row vertically
            amount_text["y_diff"] = (amount_text["top"] - main_y).abs()

            closest = amount_text.loc[amount_text["y_diff"].idxmin()]

            if closest["y_diff"] < LINE_TOLERANCE:

                results.append({
                    "description": main_row["text"],
                    "amount": closest["text"]
                })
        
        for l in results:
            amt = str(l["amount"])
            l = l["description"]
            if match(r"^\d\d/\d\d/\d\d", l):
                
                #print(l, "::::", amt, end=" ")
            
                # separating
                in_parts = []
                date_match = match(r"^\d\d/\d\d/\d\d", l)
                in_parts.append(date_match.group(0))
                l = l[len(in_parts[0]):].lstrip()

                try:
                    # cleaning nums
                    if len(amt) <3 and search(r"(-?(?:\d+,)*\d+\.\d+)$", l):
                        match = search(r"(-?(?:\d+,)*\d+\.\d+)$", l)
                        amt = match.group(0)
                    # missing numbers
                    if search(r"^(-?\.\d+)", amt):
                        amt = l[-len(amt):]
                        #print("->", amt, end="")
                    # period is comma
                    if amt[-3] == ",":
                        amt = amt[:-3] + "." + amt[-2:]
                        #print("->", amt, end="")
                    # negatives in desc
                    if "-" in l[-10:] and "-" not in amt:
                        amt = "-" + amt
                        #print("->", amt, end="")

                    amt_match = search(r"(-?(?:\d+,)*\d+\.\d+)", amt)
                    if not(amt_match):
                        # remove extra comma (4,.55)
                        if search(r"(-?(?:\d+,)*\d+\,\.\d+)", amt):
                            amt = amt[:-4] + amt[-3:]
                            #print("->", amt, end="")
                        # add period (700)
                        if search(r"(-?(?:\d+,)*\d+\d+)", amt) and amt[-3] != ".":
                            amt = amt[:-2] + "." + amt[-2:]
                            #print("->", amt, end="")
                        amt_match = search(r"(-?(?:\d+,)*\d+\.\d+)", amt)

                        l = l[:-len(amt)].rstrip()
                except:
                    amt = "MISSING"
                    #print("->", amt, end="")

                in_parts.append(l)
                in_parts.append(amt)

                # check check_line negative neighbors

                try:
                    if "-" in prev_line[2] and "-" in in_parts[2] and not "-" in check_line[2]:
                        check_line[2] = "-" + check_line[2]
                        #print("->", check_line[2], end="")
                except:
                    pass

                writer.writerow(check_line)
                prev_line = check_line
                check_line = in_parts
                #print()
