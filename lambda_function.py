
import json
import os
import uuid
import boto3
from datetime import datetime, timezone
from decimal import Decimal

# Connect to DynamoDB
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(body, default=str)
    }


def lambda_handler(event, context):
    try:
        method = event["httpMethod"]
        path_parameters = event.get("pathParameters") or {}
        product_id = path_parameters.get("id")

        # POST: Create a product
        if method == "POST":
            body = json.loads(event.get("body") or "{}")

            if not body.get("name") or "price" not in body:
                return response(400, {
                    "message": "Product name and price are required"
                })

            price = Decimal(str(body["price"]))

            if not price.is_finite() or price < 0:
                return response(400, {
                    "message": "Price must be a valid non-negative number"
                })

            product_id = str(uuid.uuid4())

            item = {
                "product_id": product_id,
                "name": body["name"],
                "price": price,
                "category": body.get("category", "General"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            table.put_item(Item=item)

            return response(201, {
                "message": "Product created successfully",
                "product": item
            })

        # GET: Retrieve all products
        elif method == "GET" and not product_id:
            result = table.scan()

            return response(200, {
                "products": result.get("Items", [])
            })

        # GET: Retrieve one product
        elif method == "GET" and product_id:
            result = table.get_item(
                Key={"product_id": product_id}
            )

            if "Item" not in result:
                return response(404, {
                    "message": "Product not found"
                })

            return response(200, result["Item"])

        # PUT: Update a product
        elif method == "PUT" and product_id:
            body = json.loads(event.get("body") or "{}")

            if not body:
                return response(400, {
                    "message": "Update information is required"
                })

            names = {}
            values = {}
            updates = []

            for field in ("name", "price", "category"):
                if field in body:
                    value = body[field]

                    if field == "price":
                        value = Decimal(str(value))
                        if not value.is_finite() or value < 0:
                            return response(400, {
                                "message": "Price must be non-negative"
                            })

                    names[f"#{field}"] = field
                    values[f":{field}"] = value
                    updates.append(f"#{field} = :{field}")

            if not updates:
                return response(400, {
                    "message": "No valid fields to update"
                })

            result = table.update_item(
                Key={"product_id": product_id},
                UpdateExpression="SET " + ", ".join(updates),
                ExpressionAttributeNames=names,
                ExpressionAttributeValues=values,
                ConditionExpression="attribute_exists(product_id)",
                ReturnValues="ALL_NEW"
            )

            return response(200, {
                "message": "Product updated successfully",
                "product": result["Attributes"]
            })

        # DELETE: Delete a product
        elif method == "DELETE" and product_id:
            table.delete_item(
                Key={"product_id": product_id},
                ConditionExpression="attribute_exists(product_id)"
            )

            return response(200, {
                "message": "Product deleted successfully",
                "product_id": product_id
            })

        else:
            return response(400, {
                "message": "Unsupported HTTP method or route"
            })

    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return response(404, {
            "message": "Product not found"
        })

    except Exception as error:
        print("ERROR:", str(error))
        return response(500, {
            "message": "Internal server error"
        })

