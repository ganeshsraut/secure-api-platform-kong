local plugin = {
  PRIORITY = 1000,
  VERSION = "1.0"
}

function plugin:access(conf)
  kong.service.request.set_header("X-Request-ID", kong.request.get_header("X-Request-ID") or "generated-id")
end

return plugin