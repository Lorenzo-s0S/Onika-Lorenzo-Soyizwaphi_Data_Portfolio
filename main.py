import pandas as pd 

df_cpi= pd.read_csv(r"C:\Users\user\OneDrive\Desktop\Portfolio Project 1\Resources\ZAFCP030000IXOBQ.csv")
r_FCE = pd.read_csv(r"C:\Users\user\OneDrive\Desktop\Portfolio Project 1\Resources\Real Final Consumption Expenditure.csv")

print("CPI Data")
#print(CPI.head())
#print(CPI.tail())
#print(CPI.describe())
#print(CPI.shape)
#print(df_cpi.columns.to_list())
df_cpi = df_cpi.iloc[:, 0].str.split(';', expand=True)##seperate the two columns and names
df_cpi.columns = ['observation_date', 'cpi_cf']
print(df_cpi.head())

##Changing the datatypes of the 2 columns
df_cpi['observation_date'] = pd.to_datetime(df_cpi['observation_date'])
df_cpi['cpi_cf'] = pd.to_numeric(df_cpi['cpi_cf'], errors='coerce')

print(df_cpi.dtypes)


'''print("real consumption expenditure data")
print(r_FCE.head())
print(r_FCE["NCRNSAXDCZAQ"].info())'''


