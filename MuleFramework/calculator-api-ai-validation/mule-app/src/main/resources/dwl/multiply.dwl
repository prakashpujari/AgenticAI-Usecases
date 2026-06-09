%dw 2.0
output application/json
---
{
  result: (payload.num1 as Number) * (payload.num2 as Number)
}
