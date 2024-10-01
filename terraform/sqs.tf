resource "aws_sqs_queue" "sre_bot_fifo_queue" {
  name                        = "sre-bot-fifo-queue.fifo"
  fifo_queue                  = true # Make sure that it is FIFO queue
  content_based_deduplication = true # Enable content-based deduplication
  delay_seconds               = 0    # Specify delay time for messages
  visibility_timeout_seconds  = 30   # Specify the visibility timeout

  depends_on = [aws_sqs_queue.sre_bot_dead_letter_queue]

  # Specify dead-letter queue (DLQ) settings
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.sre_bot_dead_letter_queue.arn
    maxReceiveCount     = 5 # Number of times a message is delivered before sending to DLQ
  })
}

# Dead-letter queue resource, which is used to store messages that cannot be processed 
resource "aws_sqs_queue" "sre_bot_dead_letter_queue" {
  name       = "sre-bot-dead-letter-queue.fifo"
  fifo_queue = true
}
