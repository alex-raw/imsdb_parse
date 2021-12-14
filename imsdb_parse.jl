mutable struct Line
    full  ::String
    clean ::String
    onset ::Union{Nothing, Int}
end

line() = Line("", "", 0)

function line(x)
    nohtml = replace(x, r"<.*?>" => "")
    clean = strip(nohtml)
    onset = findfirst(r"\S", nohtml)
    onset = isnothing(onset) ? 0 : onset[1]

    Line(x, clean, onset)
end

function pre_tag(line)
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
    tags_used = Set(String[])
    # start = r"<pre>"
    start = r"FADE IN"

    for (n, x) in enumerate(readlines(path))
        # skip until first match of `start`
        if header && !occursin(start, x)
            continue; else header = false
        end

        current = line(x)
        tag = pre_tag(current)
        push!(tags_used, tag)

        isbeginning = prev.onset - current.onset < 0
        prev.onset = current.onset

        # flush every time new block is encountered
        isbeginning && empty!(tags_used)

        # debug -----------------------------------
        # if !contains(r"^[A-Z]+$", current)
        #     continue
        # end
        # n > 500 && return
        # -----------------------------------------

        prev = current
        join([isbeginning, tags_used, tag, current], "\t", ":\t") |> println
    end
end

@time parse_script("data/Joker.html")

