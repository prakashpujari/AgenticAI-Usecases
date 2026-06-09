%dw 2.0
output application/json
var errorCode = vars.errorCode default "INTERNAL_SERVER_ERROR"
var errorMessage = vars.errorMessage default (error.description default "An unexpected error occurred")
var corrId = correlationId
---
{
  success: false,
  errorCode: errorCode,
  message: errorMessage,
  correlationId: corrId
}
