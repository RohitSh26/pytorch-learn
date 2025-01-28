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



from pyspark.sql.functions import col, lit
from pyspark.sql.types import StructType
from pyspark.sql.functions import expr, transform, lit

# Normalize the array of structs by adding missing fields
def normalize_array_of_structs(df, column_name, reference_schema):
    """
    Normalizes an array of structs by ensuring all structs contain the fields defined in the reference schema.
    Missing fields are filled with null values.
    """
    # For each field in the reference schema, create or add the missing fields
    new_struct = ", ".join([
        f"{column_name}.{field.name} AS {field.name}" if field.name in df.select(f"{column_name}.*").columns
        else f"null AS {field.name}"  # Add null for missing fields
        for field in reference_schema.fields
    ])
    df = df.withColumn(
        column_name,
        transform(
            col(column_name),
            lambda x: expr(f"struct({new_struct})")
        )
    )
    return df



def normalize_df1(df1, df2):
    """
    Normalizes all array of struct columns in df1 to match the schema of df2.
    :param df1: DataFrame coming from CosmosDB
    :param df2: DataFrame with complete schema
    :return: Normalized df1
    """
    for field in df2.schema.fields:
        # Check if the field is an array of structs
        if isinstance(field.dataType, ArrayType) and isinstance(field.dataType.elementType, StructType):
            df1 = normalize_array_of_structs(df1, field.name, field.dataType.elementType)
    return df1

def compare_dataframes(df1, df2, join_key="id"):
    """
    Compares two DataFrames using a join-based strategy.
    - Normalizes df1 to match the schema of df2.
    - Ensures schemas are aligned by adding missing columns.
    - Compares array columns as sets (order-agnostic).
    - Reports mismatches row by row and column by column.

    :param df1: First DataFrame (e.g., from CosmosDB)
    :param df2: Second DataFrame (with complete schema)
    :param join_key: Column(s) to join on (e.g., primary key).
    :return: DataFrame containing mismatched rows with column-level differences.
    """
    # Normalize df1 to match df2 schema
    df1 = normalize_df1(df1, df2)

    # Align schemas
    def align_schemas(df1, df2):
        df1_cols = set(df1.columns)
        df2_cols = set(df2.columns)

        # Add missing columns to df1
        for col_name in df2_cols - df1_cols:
            df1 = df1.withColumn(col_name, lit(None))

        # Add missing columns to df2
        for col_name in df1_cols - df2_cols:
            df2 = df2.withColumn(col_name, lit(None))

        # Ensure both DataFrames have the same column order
        common_columns = sorted(list(df1.columns))
        df1 = df1.select(common_columns)
        df2 = df2.select(common_columns)

        return df1, df2

    df1, df2 = align_schemas(df1, df2)

    # Prefix column names for join clarity
    df1_prefixed = df1.select([col(c).alias(f"df1_{c}") for c in df1.columns])
    df2_prefixed = df2.select([col(c).alias(f"df2_{c}") for c in df2.columns])

    # Join DataFrames using a FULL OUTER JOIN
    joined_df = df1_prefixed.join(
        df2_prefixed,
        on=[col(f"df1_{join_key}") == col(f"df2_{join_key}")],
        how="full_outer"
    )

    # Identify mismatched columns
    mismatch_columns = []
    for col_name in df1.columns:
        if isinstance(df1.schema[col_name].dataType, ArrayType):
            # Compare array columns as sorted strings
            mismatch_columns.append(
                when(
                    array_sort(col(f"df1_{col_name}")) != array_sort(col(f"df2_{col_name}")),
                    lit(f"Mismatch in {col_name}")
                )
            )
        elif isinstance(df1.schema[col_name].dataType, StructType):
            # Convert structs to JSON for comparison
            mismatch_columns.append(
                when(
                    to_json(col(f"df1_{col_name}")) != to_json(col(f"df2_{col_name}")),
                    lit(f"Mismatch in {col_name}")
                )
            )
        else:
            # Compare scalar columns directly
            mismatch_columns.append(
                when(
                    col(f"df1_{col_name}") != col(f"df2_{col_name}"),
                    lit(f"Mismatch in {col_name}")
                )
            )

    # Aggregate mismatch summaries
    mismatch_summary = when(lit(False), lit(None))  # Initialize an empty column
    for condition in mismatch_columns:
        mismatch_summary = mismatch_summary.otherwise(condition)

    # Add mismatch summary column to joined DataFrame
    result_df = joined_df.withColumn("mismatch_summary", mismatch_summary)

    # Filter rows with mismatches
    mismatched_rows = result_df.filter(col("mismatch_summary").isNotNull())

    return mismatched_rows

