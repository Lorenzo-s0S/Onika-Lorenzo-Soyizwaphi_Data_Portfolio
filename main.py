import pandas as pd 

CPI = pd.read_excel(r"C:\Users\user\OneDrive\Desktop\Portfolio Project 1\Resources\CPI Data For Clothing and Footwear.xlsx", sheet_name="Monthly")
r_FCE = pd.read_csv(r"C:\Users\user\OneDrive\Desktop\Portfolio Project 1\Resources\Real Final Consumption Expenditure.csv", sheet_name= "Quarterly")
print(r_FCE.head())
print(CPI.describe())

