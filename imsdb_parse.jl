using HTTP

struct Line
    full  ::String
    clean ::String
    onset ::Int
    tag   ::String
end

line() = Line("", "", 0, "")

function line(x::String)
    nohtml = replace(x, r"<.*?>" => "")
    onset = findfirst(r"\S", nohtml)

    clean = strip(nohtml)
    onset = isnothing(onset) ? 0 : onset[1]
    tag   = pre_tag(clean)

    Line(x, clean, onset, tag)
end

struct Block

end

function pre_tag(line::AbstractString)::String
    default = "UNC"
    patterns = Dict(
        "SCENE" => r"^\d+\.?\s*[A-Z]+", # scene numbers? also mostly INT/EXT
        "PAREN" => r"^\(",              # begin with paren
        "PAREN" => r"^[^\(]+\)$",       # unpaired closing paren
        "NAME"  => r"^[A-Z]+$"          # is MOM (OS) same as MOM + paren?
    )

    for (tag, pattern) in patterns
        if occursin(pattern, line)
            return tag
        end
    end
    return default
end

function parse_script(script)
    header = true
    prev = line()
    tags_used = String[]
    start = r"<pre>"
    # start = r"FADE IN"

    for (n, x) in enumerate(script)
        # skip until first match of `start`
        if header && occursin(start, x)
            header = false; else continue
        end

        current = line(x)

        # remember tags per block, flush when enter new block
        push!(tags_used, current.tag)
        is_deepest = prev.onset - current.onset < 0
        is_deepest && empty!(tags_used) # slow with `Set` maybe just `String[]`

        # debug -----------------------------------
        # if !contains(r"^[A-Z]+$", current)
        #     continue
        # end
        # n > 500 && return
        # -----------------------------------------

        prev = current
        join([is_deepest,
              tags_used,
              current.tag,
              current.clean], "\t", ":\t") |> println
    end
end

create_url(x) = join(["https://imsdb.com/scripts/", replace(x, " "=>"%20"), ".html"])
imsdb_urls(title_file) = [create_url(title) for title in readlines(title_file)]

function parse_scripts(path)
    urls = imsdb_urls(path)
    out = []
    for (i, url) = enumerate(urls[1:10])
        try
            page = split(String(HTTP.get(url)), "\n")
            push!(out, parse_script(page))
        catch e
            println(e.status)
        end
    end
    return out
end

script = split(String(HTTP.get(urls[3])), "\n")

@time parse_scripts("data/21_12_15-imsdb_titles.txt")

# @time parse_script("data/Joker.html")

