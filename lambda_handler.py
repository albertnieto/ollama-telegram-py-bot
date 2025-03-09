import json
from telegram import Update
from loguru import logger
from bot import main as get_application

def lambda_handler(event, context):
    """
    AWS Lambda handler function.
    
    Args:
        event (dict): The Lambda event
        context (object): The Lambda context
        
    Returns:
        dict: HTTP response
    """
    # Configure logging for Lambda
    logger.remove()  # Remove default handlers
    logger.add(lambda msg: print(msg), level="INFO")  # Add handler that prints to stdout
    
    logger.info("Lambda function invoked")
    
    try:
        # Extract the Telegram update from the event
        if "body" in event:
            update_data = json.loads(event["body"])
            logger.debug(f"Received update: {update_data}")
            
            # Process the update
            application = get_application(lambda_mode=True)
            if application:
                update = Update.de_json(update_data, application.bot)
                application.process_update(update)
                
                return {
                    "statusCode": 200,
                    "body": json.dumps({"message": "Update processed successfully"})
                }
            else:
                logger.error("Failed to initialize application")
                return {
                    "statusCode": 500,
                    "body": json.dumps({"message": "Failed to initialize application"})
                }
        else:
            logger.warning("No body in event")
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "No Telegram update in request body"})
            }
            
    except Exception as e:
        logger.exception(f"Error processing update: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": f"Error: {str(e)}"})
        }