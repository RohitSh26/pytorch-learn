from pyspark.sql.functions import lit, col

def align_schemas(df1, df2):
    """
    Aligns the schemas of two DataFrames by adding missing fields to both DataFrames.
    """
    schema1 = df1.schema
    schema2 = df2.schema
    
    # Extract all field names and data types from both schemas
    fields1 = {field.name: field.dataType for field in schema1.fields}
    fields2 = {field.name: field.dataType for field in schema2.fields}
    
    # Find missing fields
    missing_in_df1 = {k: v for k, v in fields2.items() if k not in fields1}
    missing_in_df2 = {k: v for k, v in fields1.items() if k not in fields2}
    
    # Add missing fields to df1
    for field, dtype in missing_in_df1.items():
        df1 = df1.withColumn(field, lit(None).cast(dtype))
    
    # Add missing fields to df2
    for field, dtype in missing_in_df2.items():
        df2 = df2.withColumn(field, lit(None).cast(dtype))
    
    return df1, df2

from pyspark.sql.functions import col
from pyspark.sql import DataFrame

def flatten_struct(df: DataFrame, prefix=""):
    """
    Flattens all nested struct columns in a DataFrame.
    """
    flat_columns = []
    for field in df.schema.fields:
        field_name = prefix + field.name
        if isinstance(field.dataType, StructType):
            # If the field is a struct, recursively flatten it
            nested_cols = flatten_struct(df.select(col(field_name + ".*")), prefix=field_name + ".")
            flat_columns.extend(nested_cols)
        else:
            flat_columns.append(col(field_name).alias(field_name.replace(".", "_")))
    return flat_columns
