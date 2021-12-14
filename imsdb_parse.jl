struct Line
    full  ::String
    clean ::String
    onset ::Int
end

line() = Line("", "", 0)

function line(x::String)
    nohtml = replace(x, r"<.*?>" => "")
    onset = findfirst(r"\S", nohtml)
    onset = isnothing(onset) ? 0 : onset[1]
    clean = strip(nohtml)

    Line(x, clean, onset)
end

function pre_tag(line::Line)::String
    default = "UNC"
    patterns = Dict(
        "SCENE" => r"^\d+\.?\s*[A-Z]+", # scene numbers? also mostly INT/EXT
        "PAREN" => r"^\(",              # begin with paren
        "PAREN" => r"^[^\(]+\)$",       # unpaired closing paren
        "NAME"  => r"^[A-Z]+$"          # is MOM (OS) same as MOM + paren?
    )

    for (tag, pattern) in patterns
        if occursin(pattern, line.clean)
            return tag
        end
    end
    return default
end

function parse_script(path)
    header = true
    prev = line()
    # tags_used = Set(String[])
    tags_used = String[]
    # start = r"<pre>"
    start = r"FADE IN"

    for (n, x) in enumerate(readlines(path))
        # skip until first match of `start`
        if header && occursin(start, x)
            header = false; else continue
        end

        current = line(x)
        tag = pre_tag(current)

        # remember tags per block, flush when enter new block
        push!(tags_used, tag)
        is_deepest = prev.onset - current.onset < 0
        is_deepest && empty!(tags_used) # slow with `Set` maybe just `String[]`

        # debug -----------------------------------
        # if !contains(r"^[A-Z]+$", current)
        #     continue
        # end
        # n > 500 && return
        # -----------------------------------------

        prev = current
        join([is_deepest, tags_used, tag, current], "\t", ":\t") |> println
    end
end

@time parse_script("data/Joker.html")

