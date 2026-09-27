## POST /v2/orders

Creates an order. The request body must be JSON and must not exceed 64 KB.

| Field | Type | Required |
|---|---|---|
| `customer_id` | string | yes |
| `items` | array | yes |
| `notes` | string | no |

Returns `201 Created` with the order object. If `items` is empty the API returns `422` and no order is created. Requests are rate-limited to 100 per minute per API key; additional requests receive `429` until the window resets.

Orders cannot be modified after 24 hours. To change an older order, cancel it and create a new one.
