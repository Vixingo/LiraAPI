import easyocr
import pandas as pd

def ocr_exchange_rate_table(image_path):
    # Initialize EasyOCR reader with Arabic and English support
    # gpu=True will run faster if an NVIDIA GPU is available
    reader = easyocr.Reader(['ar', 'en'], gpu=False)

    # Perform OCR on the image
    results = reader.readtext(image_path)

    # Print raw detected text with bounding boxes
    print("--- Detected Text Segments ---")
    extracted_data = []
    for bbox, text, confidence in results:
        print(f"Confidence: {confidence:.2f} | Text: {text}")
        extracted_data.append({"Text": text, "Confidence": confidence})

    # Return as a Pandas DataFrame for easy analysis/export
    df = pd.DataFrame(extracted_data)
    return df

if __name__ == "__main__":
    # Replace with your image file path
    image_file = "1.jfif"
    
    df = ocr_exchange_rate_table(image_file)
    
    # Save the raw extractions to CSV
    df.to_csv("ocr_output.csv", index=False)
    print("\nExtraction complete! Results saved to ocr_output.csv")