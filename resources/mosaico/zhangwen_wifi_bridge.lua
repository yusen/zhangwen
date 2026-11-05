-- ZhangWen WiFi Lua runner, for esp-claw 519bd959. No model calls.
-- Installed explicitly with a reviewed startup rule. Never runs project code at boot.
local http = require("http_server")
local capability = require("capability")
local json = require("json")
local storage = require("storage")
local app = http.app("zhangwen")
local records, count = {}, 0
local protocol = "zhangwen-wifi-lua/v1"

local function response(value, status)
  return {json = value, status = status or 200}
end
local function valid_id(id)
  return type(id) == "string" and #id == 32 and id:match("^[a-f0-9]+$")
end
local function decode(body)
  local ok, value = pcall(json.decode, body)
  if ok and type(value) == "table" then return value end
end
local function call(name, input)
  local ok, out, err = capability.call(name, input, {max_output_bytes = 16000})
  return ok, out or "", err
end
local function job(record)
  if not record.jobId then return response(record) end
  local ok, out, err = call("lua_get_async_job", {job_id = record.jobId})
  if not ok then return response({ok = false, error = err, output = out}, 409) end
  record.output = out
  record.deviceState = out:match("\nstatus=([a-z_]+)\n") or "unknown"
  return response(record)
end

app:get("/info", function()
  return response({protocol = protocol, requestCount = count, requestLimit = 200})
end)
app:post("/run", function(req)
  local body = decode(req.body)
  if not body or not valid_id(body.id) or type(body.path) ~= "string"
      or not body.path:match("^temp/zw_[a-f0-9]+%.lua$") or #body.path ~= 28
      or type(body.timeoutMs) ~= "number" or body.timeoutMs % 1 ~= 0
      or body.timeoutMs < 1000 or body.timeoutMs > 60000 then
    return response({ok = false, error = "Invalid fixed Lua manifest"}, 400)
  end
  local old = records[body.id]
  if old then
    if old.path ~= body.path or old.timeoutMs ~= body.timeoutMs then
      return response({ok = false, error = "Request id conflict"}, 409)
    end
    return response(old) -- Never invoke run again for an existing id.
  end
  if count >= 200 then return response({ok = false, error = "Receipt limit reached"}, 409) end
  local record = {id = body.id, path = body.path, timeoutMs = body.timeoutMs,
                  deviceState = "unknown", output = "Run outcome unknown"}
  records[body.id], count = record, count + 1 -- Tombstone before the only run call.
  local ok, out, err = call("lua_run_script_async", {
    path = storage.join_path(storage.get_root_dir(), "scripts", body.path),
    timeout_ms = body.timeoutMs, name = "zw_" .. body.id,
    exclusive = "zhangwen-project", replace = false, log_bytes = 8192,
  })
  record.output = out
  record.jobId = out:match("Lua job ([%w_-]+)")
  if record.jobId then return job(record) end
  record.deviceState, record.error = ok and "unknown" or "rejected", err
  return response(record)
end)
app:get("/job", function(req)
  local id = req.query.id
  if not valid_id(id) or not records[id] then return response({ok = false, error = "No receipt in this boot"}, 404) end
  return job(records[id])
end)
app:serve_forever()
