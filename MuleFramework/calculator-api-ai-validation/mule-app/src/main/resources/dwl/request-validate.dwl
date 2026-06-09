%dw 2.0
output application/json
// Validate request shape: returns a normalized request, or throws via choice-router.
var raw = payload
var hasNum1 = raw.num1?
var hasNum2 = raw.num2?
var n1Valid = hasNum1 and (raw.num1 is Number)
var n2Valid = hasNum2 and (raw.num2 is Number)
---
{
  valid: n1Valid and n2Valid,
  reason: if (!hasNum1) "num1 is required"
          else if (!hasNum2) "num2 is required"
          else if (!n1Valid) "num1 must be a number"
          else if (!n2Valid) "num2 must be a number"
          else "",
  num1: if (n1Valid) raw.num1 else null,
  num2: if (n2Valid) raw.num2 else null
}
