-- Atomic stock decrement for flash-sale hot path.
--
-- KEYS[1]  stock key  (e.g. "stock:PROD001")
--
-- Returns:
--   1   unit reserved successfully
--   0   sold out (stock <= 0)
--  -1   key does not exist (product not initialised)

local stock = redis.call('GET', KEYS[1])

if stock == false then
    return -1
end

local n = tonumber(stock)
if n <= 0 then
    return 0
end

redis.call('DECR', KEYS[1])
return 1
