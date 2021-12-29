mutable struct Line
    raw
    clean
    onset
    tag
end

line() = Line("", "", 0, "")

function line(x)
    nohtml = replace(x, r"<.*?>" => "")
    onset = findfirst(r"\S", nohtml)
    onset = isnothing(onset) ? 0 : onset[1]
    clean = strip(nohtml)
    tag   = pre_tag(clean)

    Line(x, clean, onset, tag)
end

# tag unambiguous lines. prioritized: earlier beat later patterns
function pre_tag(line)
    # any matched () or unpaired at beginning or end
    if occursin(r"^\(.*\)$|^\([^\)]+$|^[^\(]+\)$", line)
        return "PAREN"
    elseif !occursin(r"^(?!.*[a-z]).+$", line)
        return "UNC"
    end

    # Disambiguate all caps lines
    patterns = (
        "SCENE" => r"(INT|EXT)\.",               # followed by . prevents false pos
        "CUE" => r"^\d*\s*\d+.?\.?$",            # Numbers only
        "CUE" => r"^[^\(]*CONT(INUE|')D[^\)]*$", # non-parenthesized --- SCENE?
        "SPEAKER" => r"#|(1ST|2ND|3RD|\d\d?TH)", # characters are commonly numbered
        "SCENE" =>  r"^\d+[^\d]+\d*.?$",         # numbered scene titles
        "CUE" => r":|FADE|CUT",                  # assuming CAPS+colons are cues
        "EMPTY" => r"^(?!.*[A-Z]).+$",           # just non-alphanumeric
    )

    for (tag, pattern) in patterns
        if occursin(pattern, line)
            return tag
        end
    end
    return "CAPS"
end

function tag_speaker(current, prev)
    # suboptimal but hard to distunguish from other all caps lines
    speaker_pattern = r"^[A-Z\s]+([\.'-]\s?[A-Z\s]+)*(\(.*\))?$"
    if current.tag == "CAPS" &&
        occursin(speaker_pattern, current.clean) &&
        current.onset > 10 # needs testing. breaks if speakers are not indented
            current.tag = "SPEAKER"
    end
    return current.tag
end

function post_tag(current, prev, paragraph)
    # all these conditionals assume speakers and other caps are correctly tagged
    dif = prev.onset - current.onset
    if prev.tag == "SPEAKER" || prev.tag == "PAREN"
        "DIAL"
    elseif prev.tag == "SCENE" || prev.tag == "CUE"
        "INSTR"
    elseif dif == 0 || !paragraph || current.tag == "EMPTY"
        prev.tag
    elseif dif > 0
        "INSTR"
    else
        "UNC"
    end
end

function to_xml(line, tag)
    if tag == "SCENE"
        replace(line, )
    elseif tag == "SPEAKER"
    elseif tag == "PAREN"
    elseif tag == "CUE"
    elseif tag == "DIAL"
    elseif tag == "INSTR"
    elseif tag == "UNC"
    end
end

function parse_script(script; start = r"<pre", stop = r"</pre")
    prev = line()
    skip = true
    paragraph = false

    for x in readlines(script)
        if skip && !occursin(start, x)
            continue; else skip = false
        end

        current = line(x)

        if current.onset == 0
            current = prev
            paragraph = true
            continue
        end

        current.tag = tag_speaker(current, prev)

        if current.tag == "UNC" || current.tag == "CAPS"
            current.tag = post_tag(current, prev, paragraph)
        end

        # if current.tag == "SCENE"
        #     current.clean =  replace(current.clean,
        #                              r"\W*\b(.*)(.*)" => s"<scene id=\"\1\" title=\"\2\">")
        # end
        # # current.clean = to_xml(current.clean, current.tag)
        # # println(current.clean)

        # current.tag == "SCENE" &&
        # occursin(r"^(?!.*[a-z]).*\".+", current.clean) &&
        join([current.tag, current.clean], "\t", ":\t") |> println

        paragraph = false
        prev = current
        occursin(stop, x) && break
    end
end

@time begin
 parse_script("data/Matrix-Reloaded,-The.html")
 parse_script("data/Reservoir-Dogs.html")
 parse_script("data/Mighty-Joe-Young.html")
 parse_script("data/Joker.html")
 parse_script("data/Die-Hard-2.html")
end



