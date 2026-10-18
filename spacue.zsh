# spacue.zsh -- inline dropdown autocomplete for zsh
#
# Type a command, press space, and Spacue shows a dropdown of likely
# candidates right below your prompt. Arrow keys navigate, Enter or Tab
# inserts, Esc closes. Candidates you accept climb to the top -- counted
# locally, per directory. Zero dependencies, one file.
#
# https://github.com/merdanturan/spacue
# MIT License

[[ -o interactive ]] || return 0
[[ -n $_SPACUE_LOADED ]] && return 0
_SPACUE_LOADED=1
SPACUE_VERSION="0.3.0"

# ---------------------------------------------------------------- config ---
: ${SPACUE_ENABLED:=1}         # kill switch
: ${SPACUE_HINTS:=1}           # show descriptions next to items
: ${SPACUE_GENERIC:=1}         # files for unknown commands (non-empty token)
: ${SPACUE_FUZZY:=1}           # substring fallback for word providers
: ${SPACUE_TYPING_TRIGGER:=1}  # open menu when typing after "dir/" etc.
: ${SPACUE_COMPINIT:=1}        # auto-load compinit when missing
: ${SPACUE_DISABLED:=()}       # provider names to disable: npm git make ssh kill sudo paths
: ${SPACUE_MAX:=200}           # max candidates per provider
: ${SPACUE_STATS:=1}           # usage ranking: accepted candidates climb to the top (0 = off)
SPACUE_STATS_FILE="${SPACUE_STATS_FILE:-${XDG_CACHE_HOME:-$HOME/.cache}/spacue/stats.tsv}"

zmodload zsh/complist 2>/dev/null
zmodload zsh/zleparameter 2>/dev/null
zmodload zsh/stat 2>/dev/null
zmodload zsh/system 2>/dev/null
zmodload -F zsh/parameter p:commands p:aliases p:builtins p:functions 2>/dev/null

# ------------------------------------------------------------- utilities ---
typeset -gA _spacue_cache _spacue_cache_time _spacue_hascache
typeset -gA _spacue_items _spacue_match _spacue_descs
typeset -ga _spacue_items_list _spacue_match_list _spacue_descs_list

_spacue_prune_cache() {
  (( ${#_spacue_cache} > 400 )) && { _spacue_cache=(); _spacue_cache_time=() }
}

# _spacue_cached KEY TTL CMD [ARG...] -> cached stdout in REPLY.
# Call directly: command substitution would discard cache updates in a subshell.
_spacue_cached() {
  local key=$1 ttl=$2
  shift 2
  if [[ -n ${_spacue_cache[$key]+x} ]] && (( SECONDS - ${_spacue_cache_time[$key]:-0} < ttl )); then
    REPLY=${_spacue_cache[$key]}
    return 0
  fi
  local out
  out=$("$@" 2>/dev/null)
  _spacue_cached_set "$key" "$out"
  REPLY=$out
}
_spacue_cached_set() { _spacue_cache[$1]=$2; _spacue_cache_time[$1]=$SECONDS; _spacue_prune_cache; }

_spacue_has() {  # command available? (cached 30s)
  local c=$1 k="has:$1"
  if [[ -n ${_spacue_hascache[$k]+x} ]]; then (( SECONDS - ${_spacue_cache_time[$k]:-0} < 30 )) && { [[ ${_spacue_hascache[$k]} == 1 ]]; return; }; fi
  if command -v -- "$c" >/dev/null 2>&1; then _spacue_hascache[$k]=1; _spacue_cache_time[$k]=$SECONDS; return 0
  else _spacue_hascache[$k]=0; _spacue_cache_time[$k]=$SECONDS; return 1; fi
}

_spacue_mtime() {  # sets REPLY to file mtime (best effort)
  emulate -L zsh
  local -a st
  if zstat -A st +mtime -- "$1" 2>/dev/null; then REPLY=${st[1]}; return 0; fi
  REPLY=$(stat -f %m -- "$1" 2>/dev/null || stat -c %Y -- "$1" 2>/dev/null)
  [[ -n $REPLY ]]
}

_spacue_add() {  # VALUE [DESC] [MATCH]
  local v=$1 d=${2-} m=${3-$1}
  d=${d//[$'\t\n\r']/ }
  (( ${#d} > 60 )) && d="${d[1,59]}…"
  _spacue_items_list+=("$v")
  _spacue_descs_list+=("$d")
  _spacue_match_list+=("$m")
}

_spacue_add_flags() {  # CMD [SUB]
  local key=$1 ksub="$1 $2"
  # subscripts on this zsh lose meaning when quoted -- composite keys go via a variable
  [[ -n ${2-} && -n ${_spacue_flags[$ksub]+x} ]] && key="$ksub"
  [[ -n ${_spacue_flags[$key]+x} ]] || return 0
  local f
  for f in ${=_spacue_flags[$key]}; do _spacue_add "$f"; done
}

_spacue_dedup_sort() {  # dedup by value, keep order
  (( ${#_spacue_items_list} )) || return 0
  local -A seen
  local -a items=() match=() descs=()
  local i
  for i in {1..${#_spacue_items_list}}; do
    [[ -n ${seen[${_spacue_items_list[i]}]+x} ]] && continue
    seen[${_spacue_items_list[i]}]=1
    items+=("${_spacue_items_list[i]}") match+=("${_spacue_match_list[i]}") descs+=("${_spacue_descs_list[i]}")
  done
  _spacue_items_list=("${items[@]}") _spacue_match_list=("${match[@]}") _spacue_descs_list=("${descs[@]}")
}

# -------------------------------------------------------- usage ranking ---
# Accepted candidates are counted in a small local TSV file:
#
#   <key><TAB><count><TAB><dir>
#
# key is "<command>:<candidate>" (sudo/env/... wrappers are unwrapped
# first), count is how often the candidate was accepted, and the third
# field is the working directory it was accepted in (empty = global
# count).  Menus sort candidates by usage: per-directory counts count
# double, unranked candidates keep their order.  Plain TSV over
# JSON/TOML so parsing needs no external tool. Writes happen at acceptance,
# under a native zsh file lock, before the command can change directory.
# SPACUE_STATS=0 disables the feature entirely.
typeset -g _spacue_stats_cmd=""
typeset -gA _spacue_statG _spacue_statD

_spacue_stats_load() {  # small file: reread so other shells' updates are visible
  [[ -r $SPACUE_STATS_FILE ]] || { _spacue_statG=() _spacue_statD=(); return 1 }
  local raw="" l k n d
  _spacue_statG=() _spacue_statD=()
  raw=$(<$SPACUE_STATS_FILE)
  for l in ${(f)raw}; do
    [[ $l == *$'\t'* ]] || continue
    k=${l%%$'\t'*} n=${l#*$'\t'} d=${n#*$'\t'} n=${n%%$'\t'*}
    [[ -n $k && $n == <-> && ${#n} -le 9 && $d != *$'\t'* ]] || continue
    n=$(( 10#$n ))
    if [[ -z $d ]]; then
      [[ -n ${_spacue_statG[$k]+x} ]] || _spacue_statG[$k]=$n
    elif [[ $d == $PWD && -z ${_spacue_statD[$k]+x} ]]; then
      _spacue_statD[$k]=$n
    fi
  done
  return 0
}

_spacue_stats_rank() {  # bubble the candidates the user actually accepts upward
  (( ${SPACUE_STATS:-1} )) || return 0
  (( ${#_spacue_items_list} > 1 )) || return 0
  _spacue_stats_load || return 0
  emulate -L zsh
  local -a sorts=() items=() match=() descs=()
  local i sc l v k2 any=0
  for (( i = 1; i <= ${#_spacue_items_list}; i++ )); do
    v=${_spacue_items_list[i]}
    # subscripts on this zsh lose meaning when quoted -- keys go in bare
    k2="$_spacue_stats_cmd:$v"
    sc=$(( ${_spacue_statD[$k2]-0} * 2 + ${_spacue_statG[$k2]-0} ))
    # scripts accepted as "npm run <name>" also lift "npm <run-prefixed>" menus
    if [[ $v == (run|run-script|run-scripts)\ * ]]; then
      k2="$_spacue_stats_cmd:${v#* }"
      sc=$(( sc + ${_spacue_statD[$k2]-0} * 2 + ${_spacue_statG[$k2]-0} ))
    fi
    (( sc > 99999 )) && sc=99999
    (( sc > 0 )) && any=1
    # ascending on "score-complement:raw-index" => highest score first, ties keep order
    printf -v l '%05d:%010d' "$(( 99999 - sc ))" "$i"
    sorts+=( "$l" )
  done
  (( any )) || return 0
  for l in "${(@o)sorts}"; do
    i=$(( 10#${l:6} ))
    items+=("${_spacue_items_list[i]}") match+=("${_spacue_match_list[i]}") descs+=("${_spacue_descs_list[i]}")
  done
  _spacue_items_list=("${items[@]}") _spacue_match_list=("${match[@]}") _spacue_descs_list=("${descs[@]}")
}

_spacue_stats_note() {  # record at acceptance, before a command can change $PWD
  (( ${SPACUE_STATS:-1} )) || return 0
  [[ -n $_spacue_stats_cmd && -n $_spacue_pre && $BUFFER == "$_spacue_pre"* ]] || return 0
  local ins="${BUFFER#"$_spacue_pre"}"
  ins="${ins% }"   # the completion suffix
  [[ -n $ins ]] || return 0
  ins=${(Q)ins}
  [[ -n $ins ]] || return 0
  local -a keys=("$_spacue_stats_cmd:$ins")
  if [[ $ins == (run|run-script|run-scripts)\ * ]]; then
    keys+=("$_spacue_stats_cmd:${ins#* }")
  fi
  _spacue_stats_write "${keys[@]}"
}

_spacue_stats_write() {  # KEY... -- bump KEY's counts in $SPACUE_STATS_FILE
  emulate -L zsh
  (( ${SPACUE_STATS:-1} )) || return 0
  # TSV cannot represent these names; completing them still works normally.
  [[ $PWD != *[$'\t\n\r']* ]] || return 0
  local old_umask=$(umask)
  {
    umask 077
    local dir="${SPACUE_STATS_FILE:h}"
    [[ -d $dir ]] || mkdir -p -- "$dir" 2>/dev/null || return 0
    local -A want=() eg=() ed=()
    local k l n d c ol
    for k do [[ -n $k && $k != *[$'\t\n\r']* ]] && want[$k]=1; done
    (( ${#want} )) || return 0
    # Serialize read/modify/rename across terminals using zsh's native flock.
    # Never write without the lock: an unavailable cache must not break editing.
    local lockfd
    : >> "$SPACUE_STATS_FILE.lock" 2>/dev/null || return 0
    zsystem flock -t 1 -i 0.01 -f lockfd "$SPACUE_STATS_FILE.lock" 2>/dev/null || return 0
    {
      local -a out=()
      if [[ -f $SPACUE_STATS_FILE ]]; then
        for l in ${(f)"$(<$SPACUE_STATS_FILE)"}; do
          [[ $l == *$'\t'* ]] || continue
          n=${l%%$'\t'*}
          if [[ -n ${want[$n]+x} ]]; then
            d="${l#*$'\t'}"
            if [[ $d == *$'\t'* ]]; then
              c=${d%%$'\t'*} d="${d#*$'\t'}" d="${d%%$'\t'*}"
              if [[ $c == <-> && ${#c} -le 9 ]]; then
                if [[ -z $d ]]; then eg[$n]=$(( 10#$c ))
                elif [[ $d == $PWD ]]; then ed[$n]=$(( 10#$c ))
                else out+=("$l"); fi
                continue
              fi
            fi
          fi
          out+=("$l")
        done
      fi
      for k in ${(k)want}; do
        out+=("$k"$'\t'"$(( ${eg[$k]:-0} < 999999999 ? ${eg[$k]:-0} + 1 : 999999999 ))"$'\t')
        out+=("$k"$'\t'"$(( ${ed[$k]:-0} < 999999999 ? ${ed[$k]:-0} + 1 : 999999999 ))"$'\t'"$PWD")
      done
      (( ${#out} > 8000 )) && out=("${(@)out[-8000,-1]}")
      local tmp
      tmp=$(mktemp "$SPACUE_STATS_FILE.XXXXXX" 2>/dev/null) || return 0
      { for ol in "${out[@]}"; do print -r -- "$ol"; done } >| "$tmp" 2>/dev/null || {
        command rm -f -- "$tmp" 2>/dev/null; return 0; }
      mv -f -- "$tmp" "$SPACUE_STATS_FILE" 2>/dev/null || {
        command rm -f -- "$tmp" 2>/dev/null; return 0; }
    } always {
      zsystem flock -u $lockfd 2>/dev/null
    }
  } always {
    umask "$old_umask"
  }
}

_spacue_apply_filter() {  # TOKEN
  local token=$1
  local -a items=() match=() descs=()
  local i v m d lt=${(L)token}
  local flagmode=0
  [[ $token == -* ]] && flagmode=1
  local casesens=0
  [[ $SPACUE_KIND == paths ]] && casesens=1
  for (( i = 1; i <= ${#_spacue_items_list}; i++ )); do
    v=${_spacue_items_list[i]} m=${_spacue_match_list[i]} d=${_spacue_descs_list[i]}
    if (( flagmode )); then
      [[ $v == -* ]] || continue
    else
      [[ $v == -* ]] && continue
    fi
    if [[ -z $token ]]; then
      items+=("$v") match+=("$m") descs+=("$d")
    elif (( casesens )); then
      [[ $m == ${token}* ]] && { items+=("$v") match+=("$m") descs+=("$d"); }
    else
      [[ ${(L)m} == ${lt}* ]] && { items+=("$v") match+=("$m") descs+=("$d"); }
    fi
  done
  # fuzzy substring fallback (word providers only)
  if (( ! ${#items} && ! casesens && SPACUE_FUZZY )) && [[ -n $token && $flagmode == 0 ]]; then
    for (( i = 1; i <= ${#_spacue_items_list}; i++ )); do
      v=${_spacue_items_list[i]} m=${_spacue_match_list[i]} d=${_spacue_descs_list[i]}
      [[ $v == -* ]] && continue
      [[ ${(L)m} == *${lt}* ]] && { items+=("$v") match+=("$m") descs+=("$d"); }
    done
  fi
  _spacue_items_list=("${items[@]}") _spacue_match_list=("${match[@]}") _spacue_descs_list=("${descs[@]}")
}

# ------------------------------------------------------------- providers ---
# A provider is called as:  fn CMD TOKEN ARG...   (ARGS = complete words after CMD)
# It appends candidates with _spacue_add and may set SPACUE_KIND=paths|words.

typeset -gA _spacue_flags
_spacue_flags=(
  ls        '-l -a -h -t -r -R -S -1 -d -G'
  rm        '-r -f -i -v'
  cp        '-r -v -i -f'
  mv        '-v -i -f'
  mkdir     '-p -v'
  rmdir     '-p'
  grep      '-i -r -n -v -E -c -l -R'
  rg        '-i -n -l -v -c --hidden'
  find      '-name -type -maxdepth -delete'
  curl      '-L -O -o -s -I -X -H -d --compressed -v'
  ssh       '-p -i -L -R -N -v -A -Y'
  kill      '-9 -15 -1 -TERM -KILL -INT -STOP -CONT'
  sudo      '-u -i -s -E -H -k'
  'npm install'  '--save-dev -D --save -S -g --global --force --legacy-peer-deps --no-save -E --save-exact'
  'npm run'      '--silent -s'
  'pnpm install' '--save-dev -D -g --global --force'
  'yarn add'     '-D --dev --peer --exact -E'
  'git commit'   '-m --amend -a --no-verify --allow-empty --signoff'
  'git push'     '-u --set-upstream -f --force-with-lease --tags -d --delete --all'
  'git checkout' '-b -B -f --detach'
  'git reset'    '--hard --soft --mixed --keep'
  'git log'      '--oneline --graph --all --stat -p -n --decorate'
  'git clean'    '-n -f -d -x'
)

_spacue_git() {  # helper: run git in PWD
  command git -C "${PWD:-.}" "$@" 2>/dev/null
}

# --- paths (cd / ls / cat / ...) ---
_spacue_prov_paths() {
  SPACUE_KIND=paths
  local mode=$1   # dirs | all
  local token=$2
  emulate -L zsh
  local dirpfx base realdir
  if [[ $token == */ ]]; then dirpfx=$token; base=""
  elif [[ $token == */* ]]; then dirpfx=${token%/*}/; base=${token##*/}
  else dirpfx=""; base=$token; fi
  realdir=${dirpfx/#\~/$HOME}
  local -a entries
  if [[ $base == .* ]]; then
    entries=( ${realdir}${base}*(ND) )
  else
    entries=( ${realdir}${base}*(N) )
  fi
  (( ${#entries} )) || { [[ $mode == dirs ]] && _spacue_add "${dirpfx}../" "" "${dirpfx}../"; return 0 }
  local -a ditems=() fitems=()
  local e name
  for e in "${entries[@]}"; do
    name=${e#$realdir}
    if [[ -d $e ]]; then ditems+=("${name}/")
    elif [[ $mode == all ]]; then fitems+=("${name}")
    fi
  done
  ditems=( ${(oi)ditems} ) fitems=( ${(oi)fitems} )
  [[ $mode == dirs ]] && _spacue_add "${dirpfx}../" "" "${dirpfx}../"
  for name in "${ditems[@]}"; do _spacue_add "${dirpfx}${name}" "" "${dirpfx}${name}"; done
  for name in "${fitems[@]}"; do _spacue_add "${dirpfx}${name}" "" "${dirpfx}${name}"; done
}

# --- package.json helpers ---
_spacue_find_pkg() {  # walk up from $PWD; sets REPLY
  local d=${PWD:A}
  while [[ -n $d ]]; do
    [[ -f $d/package.json ]] && { REPLY=$d/package.json; return 0 }
    [[ $d == / ]] && break
    d=${d:h}
  done
  return 1
}

_spacue_pkg_data() {  # PKGPATH FIELD -> "key<TAB>value" lines in REPLY
  local pkgfile=$1 field=$2 mt key
  _spacue_mtime "$pkgfile" || mt=0
  mt=${REPLY:-0}
  key="pkg:$pkgfile:$mt:$field"
  if [[ -n ${_spacue_cache[$key]+x} ]]; then REPLY=${_spacue_cache[$key]}; return 0; fi
  local out=""
  if _spacue_has node; then
    out=$(command node -e '
      const p = require(process.argv[1]);
      const f = process.argv[2];
      const d = p[f] || {};
      for (const k of Object.keys(d).sort()) console.log(k + "\t" + String(d[k]).replace(/\s+/g, " "));
    ' "$pkgfile" "$field" 2>/dev/null)
  elif _spacue_has jq; then
    out=$(command jq -r --arg f "$field" '.[$f] // {} | to_entries | sort_by(.key)[] | "\(.key)\t\(.value)"' "$pkgfile" 2>/dev/null)
  elif _spacue_has python3; then
    out=$(command python3 -c 'import json,sys
d=json.load(open(sys.argv[1])).get(sys.argv[2]) or {}
for k in sorted(d): print("%s\t%s" % (k, str(d[k]).replace("\n"," ")))' "$pkgfile" "$field" 2>/dev/null)
  else
    out=$(awk -F'"' -v field="$field" '
      $0 ~ "\"" field "\"[ \t]*:" { ins=1 }
      ins {
        n += gsub(/\{/,"{"); m += gsub(/\}/,"}")
        if ($2 != field && NF >= 4) print $2 "\t" $4
        if (ins && n > 0 && n == m) ins=0
      }' "$pkgfile" 2>/dev/null)
  fi
  _spacue_cached_set "$key" "$out"
  REPLY=$out
}

_spacue_prov_pkgmgr() {
  local cmd=$1 token=$2
  shift 2
  local -a sargs=("$@")
  local sub=${sargs[1]-}
  SPACUE_KIND=words
  local pkg
  if _spacue_find_pkg; then pkg=$REPLY; fi

  case $sub in
    ('' )
      _spacue_pkg_prefix=1
      # scripts as "run <name>", then common subcommands
      local -a scripts deps
      if [[ -n $pkg ]]; then
        _spacue_pkg_data "$pkg" scripts
        scripts=("${(@f)REPLY}")
      fi
      local s n v
      for s in "${scripts[@]}"; do
        [[ -z $s ]] && continue
        n=${s%%$'\t'*}; v=${s#*$'\t'}
        _spacue_add "run $n" "$v" "$n"
      done
      for n in ${=_spacue_subcmds[$cmd]}; do _spacue_add "$n"; done
      ;;
    (run|run-script|run-scripts)
      [[ -n $pkg ]] || return 0
      _spacue_pkg_data "$pkg" scripts
      local -a scripts=("${(@f)REPLY}")
      local s n v
      for s in "${scripts[@]}"; do
        [[ -z $s ]] && continue
        n=${s%%$'\t'*}; v=${s#*$'\t'}
        _spacue_add "$n" "$v" "$n"
      done
      ;;
    (install|i|add|ci|update|up|remove|rm|uninstall|un|import)
      if [[ -n $pkg ]]; then
        local s n
        _spacue_pkg_data "$pkg" dependencies
        for s in "${(@f)REPLY}"; do
          [[ -z $s ]] && continue
          _spacue_add "${s%%$'\t'*}" "dep" "${s%%$'\t'*}"
        done
        _spacue_pkg_data "$pkg" devDependencies
        for s in "${(@f)REPLY}"; do
          [[ -z $s ]] && continue
          _spacue_add "${s%%$'\t'*}" "dev" "${s%%$'\t'*}"
        done
      fi
      _spacue_add_flags "$cmd" "$sub"
      ;;
  esac
}

typeset -gA _spacue_subcmds
_spacue_subcmds=(
  npm  'run test start stop restart init create publish pack link exec install i ci update outdated audit doctor cache config help version ls list why view info'
  pnpm 'run test start exec dlx install add remove update list why outdated audit patch publish pack prune store help'
  yarn 'run add remove up install dlx exec why info list outdated audit config cache node workspaces help'
  bun  'run test x install add remove update link unlink create init pm build upgrade help'
)

# --- git ---
_spacue_git_subcmds='status add commit push pull fetch checkout switch restore merge rebase branch log diff show stash remote reset revert cherry-pick clone init tag blame bisect clean config rm mv describe worktree submodule help'

_spacue_prov_git() {
  local cmd=$1 token=$2
  shift 2
  local -a sargs=("$@")
  local sub=${sargs[1]-} arg2=${sargs[2]-}
  SPACUE_KIND=paths
  case $sub in
    ('')
      local s
      for s in ${=_spacue_git_subcmds}; do _spacue_add "$s"; done
      return 0
      ;;
    (checkout|switch|merge|rebase|reset|branch|revert|cherry-pick|log|diff|show|describe)
      _spacue_git_branches
      if [[ $sub == (checkout|switch|restore) ]]; then _spacue_git_changed; fi
      _spacue_add_flags git "$sub"
      ;;
    (add|restore|rm|mv|clean)
      _spacue_git_changed
      _spacue_add_flags git "$sub"
      ;;
    (push|pull|fetch)
      if (( ${#sargs} >= 2 )) || [[ -n $arg2 ]]; then _spacue_git_branches; fi
      local r
      _spacue_cached "gitrem:$PWD" 5 _spacue_git remote
      for r in "${(@f)REPLY}"; do
        [[ -n $r ]] && _spacue_add "$r" remote "$r"
      done
      _spacue_add_flags git "$sub"
      ;;
    (stash)
      local a
      for a in push pop apply list show drop clear save; do _spacue_add "$a"; done
      ;;
    (remote)
      local a
      for a in add remove -v show set-url update prune rename; do _spacue_add "$a"; done
      ;;
    (commit)
      _spacue_git_changed
      _spacue_add_flags git commit
      ;;
  esac
}

_spacue_git_branches() {
  local out
  _spacue_cached "gitbr:$PWD" 3 _spacue_git_raw_branches
  out=$REPLY
  local b
  for b in ${(f)out}; do
    [[ -z $b ]] && continue
    [[ $b == '(HEAD detached'* ]] && continue
    _spacue_add "$b" branch "$b"
  done
}
_spacue_git_raw_branches() {
  _spacue_git branch --format='%(refname:short)' || \
    _spacue_git branch --no-color | sed -e 's/^[*+ ] //' -e 's/ -> .*//'
}

_spacue_git_changed() {
  local out
  _spacue_cached "gitst:$PWD" 3 _spacue_git status --porcelain
  out=$REPLY
  local l st p
  for l in ${(f)out}; do
    [[ -z $l ]] && continue
    st=${l[1,2]}
    p=${l[4,-1]}
    p=${p%% -> *}
    [[ $p == \"*\" ]] && p=${p[2,-2]}
    [[ -z $p ]] && continue
    _spacue_add "$p" "${st// /}" "$p"
  done
}

# --- make ---
_spacue_prov_make() {
  SPACUE_KIND=words
  local mf
  for mf in Makefile makefile GNUmakefile; do
    [[ -f $mf ]] && break
    mf=""
  done
  [[ -n $mf ]] || return 0
  local mt key out
  _spacue_mtime "$mf" || mt=0
  mt=${REPLY:-0}
  key="make:$PWD:$mf:$mt"
  if [[ -n ${_spacue_cache[$key]+x} ]]; then out=${_spacue_cache[$key]} else
    out=$(awk '
      /^[a-zA-Z0-9][a-zA-Z0-9_.-]*[ \t]*:/ {
        line=$0; name=line; sub(/[ \t]*:.*/,"",name);
        desc="";
        if (match(line, /##[ \t]*/)) desc=substr(line, RSTART+RLENGTH);
        gsub(/[ \t]+$/,"",desc);
        print name "\t" desc
      }' "$mf" 2>/dev/null)
    _spacue_cached_set "$key" "$out"
  fi
  local l n v
  for l in ${(f)out}; do
    [[ -z $l ]] && continue
    n=${l%%$'\t'*}; v=${l#*$'\t'}
    _spacue_add "$n" "${v:--}" "$n"
  done
}

# --- ssh hosts ---
_spacue_prov_ssh() {
  SPACUE_KIND=words
  local out
  _spacue_cached "ssh:$HOME" 10 _spacue_ssh_raw
  out=$REPLY
  local h
  for h in ${(f)out}; do
    [[ -n $h ]] && _spacue_add "$h" host "$h"
  done
}
_spacue_ssh_raw() {
  {
    [[ -f ~/.ssh/config ]] && awk 'tolower($1)=="host" { for (i=2;i<=NF;i++) print $i }' ~/.ssh/config
    if [[ -f ~/.ssh/known_hosts ]]; then
      grep -v '^@' ~/.ssh/known_hosts | awk '{print $1}'
      [[ -f ~/.ssh/known_hosts2 ]] && grep -v '^@' ~/.ssh/known_hosts2 | awk '{print $1}'
    fi
  } 2>/dev/null | sed -E 's/^\[//; s/\](:[0-9]+)?$//; s/,.*//' | grep -vE '[*?!]' | sort -u
}

# --- kill / killall ---
_spacue_prov_kill() {
  SPACUE_KIND=words
  local cmd=$1
  local out
  _spacue_cached "ps:$cmd" 2 _spacue_ps_raw
  out=$REPLY
  local -a lines=(${(f)out})
  # kill targets are listed newest-first so the cap keeps the processes the
  # user is most likely after (the ones they just started).
  [[ $cmd == kill ]] && lines=(${(On)lines})
  local l pid comm
  for l in "${lines[@]}"; do
    [[ -z $l ]] && continue
    pid=${l%%$'\t'*}
    comm=${l#*$'\t'}
    if [[ $cmd == kill ]]; then _spacue_add "$pid" "$comm" "$pid"
    else _spacue_add "$comm" "$pid" "$comm"
    fi
  done
  _spacue_add_flags "$cmd"
}
_spacue_ps_raw() {
  ps -axo pid=,comm= 2>/dev/null | awk '{ pid=$1; $1=""; sub(/^ /,""); comm=$0; n=split(comm,a,"/"); print pid "\t" a[n] }'
}

# --- sudo / env / wrappers ---
_spacue_prov_cmds() {
  SPACUE_KIND=words
  local cmd=$1
  local out
  _spacue_cached "cmds" 30 _spacue_cmds_raw
  out=$REPLY
  local c
  for c in ${(f)out}; do
    [[ -n $c ]] && _spacue_add "$c" "" "$c"
  done
  _spacue_add_flags "$cmd"
}
_spacue_cmds_raw() {
  emulate -L zsh
  local -a cmds
  (( ${#commands} )) && cmds+=(${(k)commands})
  (( ${#aliases} )) && cmds+=(${(k)aliases})
  (( ${#builtins} )) && cmds+=(${(k)builtins})
  (( ${#functions} )) && cmds+=(${(k)functions})
  print -rl -- ${(ou)cmds}
}

# --- dispatch ---
typeset -gA _spacue_builtin_providers
_spacue_builtin_providers=(
  npm  _spacue_prov_pkgmgr
  pnpm _spacue_prov_pkgmgr
  yarn _spacue_prov_pkgmgr
  bun  _spacue_prov_pkgmgr
  git  _spacue_prov_git
  make _spacue_prov_make
  gmake _spacue_prov_make
  ssh  _spacue_prov_ssh
  scp  _spacue_prov_ssh
  sftp _spacue_prov_ssh
  kill _spacue_prov_kill
  killall _spacue_prov_kill
  pkill _spacue_prov_kill
  sudo _spacue_prov_cmds
  doas _spacue_prov_cmds
  env  _spacue_prov_cmds
  nohup _spacue_prov_cmds
  time _spacue_prov_cmds
  command _spacue_prov_cmds
  xargs _spacue_prov_cmds
  exec _spacue_prov_cmds
  nice _spacue_prov_cmds
)
typeset -gA _spacue_pathcmds
_spacue_pathcmds=(
  cd 1 pushd 1 ls 1 cat 1 bat 1 less 1 more 1 head 1 tail 1 vim 1 nvim 1 vi 1 view 1
  code 1 code-insiders 1 open 1 rm 1 rmdir 1 cp 1 mv 1 mkdir 1 touch 1 ln 1 chmod 1 chown 1
  stat 1 file 1 du 1 df 1 find 1 grep 1 rg 1 sed 1 awk 1 sort 1 uniq 1 wc 1 diff 1 patch 1
  python 1 python3 1 node 1 ruby 1 perl 1 zip 1 unzip 1 tar 1 gzip 1 gunzip 1 xxd 1 od 1
  hexdump 1 tee 1 source 1 . 1
)
typeset -gA _spacue_wrappers
_spacue_wrappers=( sudo 1 doas 1 env 1 nohup 1 time 1 command 1 xargs 1 nice 1 exec 1 )
typeset -gA _spacue_providers   # user-registered providers

# ------------------------------------------------------- collect + parse ---
SPACUE_KIND=""

_spacue_quote_ok() {  # ignore escaped quotes; reject unfinished tokens
  emulate -L zsh
  local quote="" escaped=0 char
  local i
  for (( i = 1; i <= ${#1}; i++ )); do
    char=${1[i]}
    if (( escaped )); then escaped=0; continue; fi
    if [[ $quote == "'" ]]; then
      [[ $char == "'" ]] && quote=""
    elif [[ $char == '\' ]]; then
      escaped=1
    elif [[ -n $quote ]]; then
      [[ $char == "$quote" ]] && quote=""
    elif [[ $char == "'" || $char == '"' ]]; then
      quote=$char
    fi
  done
  [[ -z $quote && $escaped == 0 ]]
}

_spacue_collect_from_buffer() {
  emulate -L zsh
  _spacue_items_list=() _spacue_match_list=() _spacue_descs_list=()
  _spacue_token=""
  SPACUE_KIND=""
  local left=$LBUFFER
  [[ -n $left ]] || return 1
  _spacue_quote_ok "$left" || return 1
  local -a words=(${(z)left})
  # Complete the current simple command after a pipeline/list separator.
  # Stop at redirections and substitutions rather than guessing their grammar.
  local i
  for (( i = ${#words}; i >= 1; i-- )); do
    case ${words[i]} in
      ('|'|'||'|'&&'|';'|'&') words=("${(@)words[$(( i + 1 )),-1]}"); break ;;
      ('<'|'>'|'>>'|'<<'|'<<<'|'$('|'`') return 1 ;;
    esac
  done
  local token=""
  if [[ $left == *[[:space:]] ]]; then token=""
  else token="${words[-1]}"; fi
  local -a sargs
  if [[ -z $token ]]; then sargs=("${words[@]}")
  else sargs=("${(@)words[1,$(( ${#words} - 1 ))]}"); fi
  (( ${#sargs} )) || return 1
  local cmd=${sargs[1]}
  [[ -n $cmd ]] || return 1
  sargs=("${(@)sargs[2,-1]}")
  # unwrap sudo/env/... chains
  while (( ${#sargs} )) && [[ -n ${_spacue_wrappers[$cmd]+x} && ${sargs[1]} != -* ]]; do
    cmd=${sargs[1]}
    sargs=("${(@)sargs[2,-1]}")
  done
  _spacue_token=$token
  local rc=1
  _spacue_dispatch "$cmd" "${(Q)token}" "${sargs[@]}"; rc=$?
  return $rc
}

_spacue_dispatch() {
  local cmd=$1 token=$2
  shift 2
  local -a sargs=("$@")
  SPACUE_KIND=""
  _spacue_pkg_prefix=""
  _spacue_stats_cmd=$cmd
  local fn=""
  local d
  for d in ${=_spacue_disabled_arr}; do
    [[ $d == $cmd ]] && { fn="__disabled__"; break }
  done
  if [[ $fn == __disabled__ ]]; then :
  elif [[ -n ${_spacue_providers[$cmd]+x} ]]; then fn=${_spacue_providers[$cmd]}
  elif [[ -n ${_spacue_builtin_providers[$cmd]+x} ]]; then fn="__builtin__:${_spacue_builtin_providers[$cmd]}"
  fi
  case $fn in
    (__disabled__)
      if [[ -n ${_spacue_pathcmds[$cmd]+x} ]]; then _spacue_prov_paths all "$token"; fi
      ;;
    ('' )
      if [[ -n ${_spacue_pathcmds[$cmd]+x} ]]; then
        if [[ $cmd == (cd|pushd) ]]; then _spacue_prov_paths dirs "$token"
        else _spacue_prov_paths all "$token"; fi
      elif (( SPACUE_GENERIC )); then
        _spacue_prov_paths all "$token"
      fi
      ;;
    (__builtin__:* )
      "${fn#__builtin__:}" "$cmd" "$token" "${sargs[@]}"
      ;;
    (*)
      "$fn" "$cmd" "$token" "${sargs[@]}"
      ;;
  esac
  # flag fallback: "-<...>" offers the flags table even for plain path commands
  if [[ $token == -* && -n ${_spacue_flags[$cmd]+x} ]]; then
    _spacue_add_flags "$cmd"
  fi
  _spacue_dedup_sort
  # central filter
  [[ -z $SPACUE_KIND ]] && SPACUE_KIND=words
  if [[ $cmd == (cd|pushd) ]]; then SPACUE_KIND=paths; fi
  if [[ -n ${_spacue_pathcmds[$cmd]+x} && -z ${_spacue_builtin_providers[$cmd]+x} ]]; then SPACUE_KIND=paths; fi
  _spacue_apply_filter "$token"
  _spacue_stats_rank
  (( ${#_spacue_items_list} > SPACUE_MAX )) && {
    _spacue_items_list=("${(@)_spacue_items_list[1,$SPACUE_MAX]}")
    _spacue_match_list=("${(@)_spacue_match_list[1,$SPACUE_MAX]}")
    _spacue_descs_list=("${(@)_spacue_descs_list[1,$SPACUE_MAX]}")
  }
  (( ${#_spacue_items_list} ))
}

typeset -ga _spacue_disabled_arr
_spacue_disabled_arr=(${=SPACUE_DISABLED})

# ------------------------------------------------- completion plumbing -----
# Spacue feeds its candidates into the *standard* completion machinery via
# the `completer` style instead of a custom zle -C widget.  That keeps
# native menu selection, listing, colours and zstyle formatting intact.
_spacue_completer() {  # runs inside the completion system while pending
  (( ${#_spacue_items_list} )) || return 1
  local -a items=("${_spacue_items_list[@]}") disp
  local i
  if (( SPACUE_HINTS )); then
    for i in {1..${#items}}; do
      if [[ -n ${_spacue_descs_list[i]-} ]]; then
        disp+=("${items[i]}  -- ${_spacue_descs_list[i]}")
      else
        disp+=("${items[i]}")
      fi
    done
  else
    disp=("${items[@]}")
  fi
  # Split for native suffix handling: dir-like candidates (trailing slash)
  # go in with -S '' so zsh appends nothing on accept (like native dir
  # completion), everything else behaves like a completed word (space
  # appended).  Both calls share the -V group so the visible order is kept.
  local -a ditems didisp iitems iidisp
  local j
  for j in {1..${#items}}; do
    if [[ ${items[j]} == */ ]]; then ditems+=("${items[j]}") didisp+=("${disp[j]}")
    else iitems+=("${items[j]}") iidisp+=("${disp[j]}"); fi
  done
  if [[ ${items[1]} == ${_spacue_token-}* ]]; then
    (( ${#ditems} )) && compadd -S '' -V spacue -d didisp -a ditems
    (( ${#iitems} )) && compadd -V spacue -d iidisp -a iitems
  else
    # fuzzy fallback produced non-prefix matches: add them as-is
    (( ${#ditems} )) && compadd -S '' -U -V spacue -d didisp -a ditems
    (( ${#iitems} )) && compadd -U -V spacue -d iidisp -a iitems
  fi
}
_spacue_completer_style() {  # zstyle -e answer function
  if [[ -n $_spacue_pending ]]; then
    reply=(_spacue_completer)
  elif [[ $_spacue_saved_completer == "__unset__" ]]; then
    reply=(_complete)
  else
    reply=("${_spacue_saved_completer[@]}")
  fi
}

# ---------------------------------------------------- menu open / state ---
typeset -g _spacue_on _spacue_pre _spacue_typed _spacue_pending _spacue_fires _spacue_menufires
typeset -g _spacue_saved_menu _spacue_saved_verbose _spacue_saved_completer
typeset -g _spacue_styles_saved
typeset -g _spacue_shields_up _spacue_esc_taken _spacue_beep_saved
typeset -gA _spacue_prev_main_tab
typeset -gA _spacue_prev_menu_keys
typeset -g _spacue_firekey=$'\e[991~'

_spacue_style_on() {
  [[ -n $_spacue_styles_saved ]] && return 0
  emulate -L zsh
  local -a v
  if zstyle -a ':completion:*' menu v; then _spacue_saved_menu=("${v[@]}"); else _spacue_saved_menu="__unset__"; fi
  if zstyle -a ':completion:*' verbose v; then _spacue_saved_verbose=("${v[@]}"); else _spacue_saved_verbose="__unset__"; fi
  if zstyle -a ':completion:*' completer v; then _spacue_saved_completer=("${v[@]}"); else _spacue_saved_completer="__unset__"; fi
  zstyle ':completion:*' menu select
  zstyle -e ':completion:*' completer _spacue_completer_style
  (( SPACUE_HINTS )) && zstyle ':completion:*' verbose yes
  _spacue_styles_saved=1
}
_spacue_style_off() {
  [[ -n $_spacue_styles_saved ]] || return 0
  emulate -L zsh
  if [[ $_spacue_saved_menu == "__unset__" ]]; then zstyle -d ':completion:*' menu
  else zstyle ':completion:*' menu "${_spacue_saved_menu[@]}"; fi
  if [[ $_spacue_saved_verbose == "__unset__" ]]; then zstyle -d ':completion:*' verbose
  else zstyle ':completion:*' verbose "${_spacue_saved_verbose[@]}"; fi
  if [[ $_spacue_saved_completer == "__unset__" ]]; then zstyle -d ':completion:*' completer
  else zstyle ':completion:*' completer "${_spacue_saved_completer[@]}"; fi
  _spacue_saved_menu="" _spacue_saved_verbose="" _spacue_saved_completer=""
  _spacue_styles_saved=""
}

# Quiet open/close helpers.  While a Spacue menu is active we silence the
# listing beep (listbeep) and install temporary "shield" bindings so that
# Esc/Ctrl-G can cancel the menu cleanly.  Everything is reverted by
# _spacue_cleanup_state.
_spacue_beep_off() {
  [[ -n $_spacue_beep_saved ]] && return 0
  _spacue_beep_saved=0
  if [[ -o listbeep ]]; then
    _spacue_beep_saved=1
    unsetopt listbeep
  fi
}
_spacue_beep_restore() {
  [[ -n $_spacue_beep_saved ]] || return 0
  (( _spacue_beep_saved )) && setopt listbeep
  _spacue_beep_saved=""
}

# This widget's body never runs inside the menu loop: complist only looks at
# the widget flags.  A zle -C (completion) widget bound in the `menuselect`
# keymap makes the loop exit via `acc = 0; broken = 2` -- the menu is left
# and the key is re-dispatched through the regular keymap, where our
# spacue-esc / spacue-send-break / spacue-list-expand / vi-cmd-mode
# wrappers drop the Spacue state and return to the prompt with the typed
# text intact.
_spacue_dismiss_rc() { return 1 }

_spacue_shields_on() {
  [[ -n $_spacue_shields_up ]] && return 0
  _spacue_shields_up=1
  zmodload -e zsh/complist 2>/dev/null || return 0
  local key binding
  for key in '^[' '^G' '^I'; do
    binding=$(bindkey -M menuselect "$key")
    _spacue_prev_menu_keys[$key]=${binding##* }
  done
  bindkey -M menuselect '^[' spacue-dismiss 2>/dev/null
  bindkey -M menuselect '^G' spacue-dismiss 2>/dev/null
  # Tab accepts the highlighted selection exactly like Enter (the usual
  # completion convention).  The stock menuselect binding is recorded and
  # restored when the menu closes, so native zsh menus keep their own
  # Tab behaviour.
  bindkey -M menuselect '\t' accept 2>/dev/null
  local map
  for map in emacs viins; do
    binding=$(bindkey -M "$map" '^I')
    _spacue_prev_main_tab[$map]=${binding##* }
    bindkey -M "$map" '^I' spacue-accept
  done
  # Bare Esc is undefined-key in the stock emacs keymap; take it over only
  # then (viins binds it to vi-cmd-mode, which has its own wrapper).
  [[ $(bindkey -M emacs '^[' 2>/dev/null) == *undefined-key* ]] && {
    bindkey -M emacs '^[' spacue-esc 2>/dev/null
    _spacue_esc_taken=1
  }
}
_spacue_shields_off() {
  [[ -n $_spacue_shields_up ]] || return 0
  _spacue_shields_up=""
  local map
  for map in emacs viins; do
    [[ $(bindkey -M "$map" '^I') == *spacue-accept ]] &&
      bindkey -M "$map" '^I' "${_spacue_prev_main_tab[$map]}"
  done
  _spacue_prev_main_tab=()
  local key
  for key in '^[' '^G' '^I'; do
    bindkey -M menuselect "$key" "${_spacue_prev_menu_keys[$key]}" 2>/dev/null
  done
  _spacue_prev_menu_keys=()
  if [[ -n $_spacue_esc_taken ]]; then
    _spacue_esc_taken=""
    [[ $(bindkey -M emacs '^[' 2>/dev/null) == *spacue-esc* ]] && bindkey -M emacs -r '^[' 2>/dev/null
  fi
}

# A dismissed menu hands zsh's pre-menu copy of the line back.  For fuzzy
# (-U) candidate lists that copy is missing the typed filter text: the
# insert phase replaced the token with the candidates' (empty) common
# prefix, which leaves exactly the pre-part of the line behind.  When that
# signature is found, rebuild the line from the typed state -- otherwise
# the visible line (a typing-trigger prefix insert, a progressive
# single-match insert, the typed text itself) is kept as-is.
_spacue_fix_dismissed_line() {
  [[ -n $_spacue_on ]] || return 0
  [[ $BUFFER == "$_spacue_pre" ]] || return 0
  BUFFER="${_spacue_pre}${_spacue_typed}"
  CURSOR=${#BUFFER}
}

_spacue_esc() {  # re-dispatched Esc from a dismissed menu
  if [[ -n $_spacue_on ]]; then
    _spacue_fix_dismissed_line
    _spacue_cleanup_state
  fi
  zle -Rc 2>/dev/null
  return 0
}

_spacue_cleanup_state() {
  # Native completion quotes each candidate as one word. Only package-menu
  # "run <script>" entries contain a deliberate separator; preserve quoting
  # inside script names and in every other provider's arguments.
  if [[ -n $_spacue_pkg_prefix && -n $_spacue_pre && $BUFFER == "$_spacue_pre"* ]]; then
    local ins="${BUFFER#"$_spacue_pre"}" suffix="" candidate
    [[ $ins == *' ' ]] && { ins=${ins% }; suffix=' '; }
    ins=${(Q)ins}
    for candidate in "${_spacue_items_list[@]}"; do
      if [[ $ins == "$candidate" ]]; then
        _spacue_format_item "$candidate"
        BUFFER="$_spacue_pre$REPLY$suffix" CURSOR=${#BUFFER}
        break
      fi
    done
  fi
  _spacue_on="" _spacue_pre="" _spacue_typed="" _spacue_pending="" _spacue_fires="" _spacue_menufires=""
  _spacue_beep_restore
  _spacue_shields_off
  _spacue_style_off
}

_spacue_format_item() {  # raw candidate -> safe shell insertion in REPLY
  local item=$1
  if [[ -n $_spacue_pkg_prefix && $item == 'run '* ]]; then
    item=${item#run }
    REPLY="run ${(q)item}"
  else
    REPLY=${(q)item}
  fi
}

_spacue_replace_token() {  # ITEM -- replace current token with ITEM
  _spacue_format_item "$1"
  local item=$REPLY
  local keep=$(( ${#BUFFER} - ${#_spacue_token} ))
  if (( keep > 0 )); then BUFFER="${BUFFER[1,$keep]}${item}" else BUFFER="${item}" fi
  CURSOR=${#BUFFER}
}

_spacue_fire() {  # one completion attempt per invocation
  local before=$BUFFER
  zle complete-word
  (( _spacue_fires = ${_spacue_fires:-0} + 1 ))
  if (( _spacue_fires == 1 )); then
    # The first attempt is zsh's "insert common prefix" phase.  When it
    # changed the line it did not list anything, so two more attempts are
    # needed -- list, then menu -- and the menu sits two fires from here.
    # (A no-change first attempt already lists; the menu comes next.)
    if [[ $BUFFER != $before ]]; then
      _spacue_menufires=3
      # Fuzzy lists (-U) have no common prefix with the token, so this
      # insert phase rewrites or wipes it (`npm run i` -> `npm run `).
      # The typed filter text is kept in _spacue_pre/_spacue_typed; typing
      # rebuilds the line from it, and the dismiss wrappers restore it.
      zle -U "$_spacue_firekey"
      return 0
    fi
    _spacue_menufires=2
    return 0
  fi
  if (( _spacue_fires >= _spacue_menufires )); then
    # The menu attempt has just finished (any earlier fires were prefix
    # insert / listing).  The completion system acts on its own again, so
    # our candidates are dropped before the next Tab press.  When the menu
    # was accepted with Enter the line changed and nothing is queued
    # behind the completion; that is the end of the Spacue state.  (Typing
    # mid-menu ungets the typed key and Esc/C-g unget the dismiss key, so
    # KEYS_QUEUED_COUNT > 0 there -- those paths keep the state for their
    # re-dispatched keys to clean up.)
    _spacue_pending=""
    if [[ $BUFFER != $before ]]; then
      # A Tab-accept leaves exactly one byte in the input queue: the original
      # Tab re-dispatched by the menu machinery (Enter and menu-open leave
      # none).  Pop that one byte: a Tab means the completion was accepted,
      # so the Spacue state can end cleanly right here -- the swallowed Tab
      # never reaches the stock widget again, which is what used to let the
      # stock completion (git pathspecs, npm scripts, ...) append its own
      # candidate after the accepted one.  Any non-Tab queued byte is
      # type-ahead or a dismissal key arriving mid-menu; those own their
      # handling later, so push the byte back unchanged.
      if (( ${KEYS_QUEUED_COUNT:-0} == 1 )); then
        local _spacue_qk=""
        if read -t 0 -k _spacue_qk 2>/dev/null; then
          if [[ $_spacue_qk == $'\t' ]]; then
            _spacue_stats_note
            _spacue_cleanup_state
          else
            zle -U "$_spacue_qk"
          fi
        fi
      fi
      if [[ -n $_spacue_on && ${KEYS_QUEUED_COUNT:-0} -eq 0 ]]; then
        _spacue_stats_note
        _spacue_cleanup_state
      fi
    fi
  fi
  # a non-zero rc here makes zle beep after the menu closes; the menu
  # itself already provides all the feedback we need
  return 0
}

# Open the menu: queue two completion fires.  The first lists the matches,
# the second starts native menu selection (same as pressing Tab twice).
_spacue_show_menu() {
  _spacue_on=1
  _spacue_style_on
  _spacue_beep_off
  _spacue_shields_on
  _spacue_pending=1
  _spacue_fires=0
  _spacue_menufires=0
  zle -U "$_spacue_firekey$_spacue_firekey"
}

# open / reopen from current buffer state (assumes collect already ran)
_spacue_open_here() {
  (( ${#_spacue_items_list} )) || return 1
  local toklen=${#_spacue_token}
  if (( toklen )); then _spacue_pre="${BUFFER[1,$(( ${#BUFFER} - toklen ))]}" else _spacue_pre="$BUFFER"; fi
  _spacue_typed=$_spacue_token
  if (( ${#_spacue_items_list} == 1 )); then
    if [[ ${_spacue_items_list[1]} == ${(Q)_spacue_token}../ ]]; then
      # The only candidate is the parent link of an empty directory: the
      # user already typed the directory itself ("cd beta/"), so don't
      # rewrite it to "cd beta/../".
      _spacue_cleanup_state
      return 0
    fi
    _spacue_replace_token "${_spacue_items_list[1]}"
    _spacue_on=1
    _spacue_shields_on
    return 0
  fi
  _spacue_show_menu
}

# reopen after typing/backspace while menu is active
_spacue_reopen() {  # BASE
  local base=$1
  BUFFER="$base" CURSOR=${#BUFFER}
  if ! _spacue_collect_from_buffer; then _spacue_cleanup_state; return 0; fi
  if (( ! ${#_spacue_items_list} )); then _spacue_cleanup_state; return 0; fi
  local toklen=${#_spacue_token}
  if (( toklen )); then _spacue_pre="${BUFFER[1,$(( ${#BUFFER} - toklen ))]}" else _spacue_pre="$BUFFER"; fi
  _spacue_typed=$_spacue_token
  if (( ${#_spacue_items_list} == 1 )); then
    # Progressive typing: show the single candidate live but keep the state
    # so the next keystroke re-filters from what was typed (otherwise the
    # auto-inserted text would clobber further typing).
    [[ ${_spacue_items_list[1]} == ${(Q)_spacue_token}../ ]] && return 0
    _spacue_replace_token "${_spacue_items_list[1]}"
    return 0
  fi
  _spacue_show_menu
}

# ------------------------------------------------------------- triggers ---
_spacue_try_trigger() {  # MODE
  local mode=$1
  # Menus are built on the completion system.  If it is not loaded (bare
  # zsh with SPACUE_COMPINIT=0), stay completely out of the way: no state,
  # no queued completion attempts -- space just types a space.
  (( $+functions[_main_complete] )) || return 0
  case $mode in
    (space)
      _spacue_collect_from_buffer || return 0
      (( ${#_spacue_items_list} )) || return 0
      _spacue_open_here
      ;;
    (slash)
      (( SPACUE_TYPING_TRIGGER )) || return 0
      _spacue_collect_from_buffer || return 0
      (( ${#_spacue_items_list} )) || return 0
      [[ $SPACUE_KIND == paths || $_spacue_token == (\.*|/*|~*) ]] || return 0
      _spacue_open_here
      ;;
    (typing)
      (( SPACUE_TYPING_TRIGGER )) || return 0
      local first=${LBUFFER%%[[:space:]]*}
      [[ -n ${_spacue_pathcmds[$first]+x} ]] || return 0
      local lw=${LBUFFER##*[[:space:]]}
      [[ $lw == */* ]] || return 0
      _spacue_collect_from_buffer || return 0
      (( ${#_spacue_items_list} )) || return 0
      _spacue_open_here
      ;;
  esac
}

# ------------------------------------------------------- widget wrappers ---
_spacue_self_insert() {
  if [[ -n $_spacue_on ]]; then
    # Typing while a menu is live (the key that ends menu-select, plus any
    # key typed ahead of it).  The line may still show completion preview
    # text or a half-restored buffer, so rebuild it from the canonical
    # typed state -- pre + typed + key -- before re-filtering.  Fast typing
    # (type-ahead, paste) then lands every key exactly once instead of
    # dropping keys into the preview or losing the filter base.
    BUFFER="${_spacue_pre}${_spacue_typed}"
    CURSOR=${#BUFFER}
    zle _spacue_ins
    (( SPACUE_ENABLED )) && _spacue_reopen "$BUFFER"
    return 0
  fi
  zle _spacue_ins
  (( SPACUE_ENABLED )) || return 0
  (( ${PENDING:-0} )) && return 0
  (( CURSOR == ${#BUFFER} )) || return 0
  case $KEYS in
    (' ') _spacue_try_trigger space ;;
    ('/') _spacue_try_trigger slash ;;
    (*)   _spacue_try_trigger typing ;;
  esac
}

_spacue_backward_delete_char() {
  if [[ -n $_spacue_on ]]; then
    local typed=$_spacue_typed base
    if [[ -n $typed ]]; then
      typed="${typed[1,$(( ${#typed} - 1 ))]}"
      _spacue_reopen "${_spacue_pre}${typed}"
    else
      base="${_spacue_pre[1,$(( ${#_spacue_pre} - 1 ))]}"
      _spacue_cleanup_state
      BUFFER="$base" CURSOR=${#BUFFER}
    fi
    return 0
  fi
  zle _spacue_bdel
}

_spacue_accept_line() {
  if [[ -n $_spacue_on ]]; then
    _spacue_stats_note
    _spacue_cleanup_state
    return 0
  fi
  zle _spacue_accept
}

_spacue_send_break() {
  if [[ -n $_spacue_on ]]; then
    # Cancel the pending Spacue state (menu already dismissed) without
    # aborting the line: the typed text stays put and the next key works.
    _spacue_fix_dismissed_line
    _spacue_cleanup_state
    zle -Rc 2>/dev/null
    return 0
  fi
  zle _spacue_sbreak
}

_spacue_list_expand() {
  if [[ -n $_spacue_on ]]; then
    _spacue_fix_dismissed_line
    _spacue_cleanup_state
    zle -Rc 2>/dev/null
    return 0
  fi
  zle _spacue_lexpand
}

_spacue_vi_cmd_mode() {
  if [[ -n $_spacue_on ]]; then
    _spacue_fix_dismissed_line
    _spacue_cleanup_state
    zle -Rc 2>/dev/null
  fi
  zle _spacue_vicmd
}

# Menu integration notes: complist provides a bindable `menuselect` keymap.
# While a Spacue menu is open, bare Esc and Ctrl-G in `menuselect` are bound
# to spacue-dismiss, a zle -C stub: the menu loop exits with the original
# line restored and the key is re-dispatched through the regular keymap,
# where the spacue-esc (emacs Esc), send-break, list-expand and vi-cmd-mode
# wrappers below drop the Spacue state quietly and clear leftover listings.
# These `menuselect` bindings exist only while Spacue state is active --
# _spacue_cleanup_state reverts them -- so native zsh menus are completely
# untouched (bare Esc keeps its stock prefix behaviour there).  Enter and
# Tab both accept a selection (Tab's stock binding is restored on close);
# a second Enter executes the inserted line.  Note: a *bare* Esc waits
# KEYTIMEOUT (0.4s by default) for a longer escape sequence; any following
# key resolves the wait immediately, so snacky typists rarely notice it.

# ------------------------------------------------------------- bootstrap ---
_spacue_precmd() {
  _spacue_cleanup_state
}

_spacue_install() {
  # The standard completion system is required: menu selection, the completer
  # dispatch and all zstyles live in it.  Load it quietly if the user's setup
  # has not (SPACUE_COMPINIT=0 opts out).
  if (( ${SPACUE_COMPINIT:-1} )) && (( ! $+functions[_main_complete] )); then
    autoload -Uz compinit 2>/dev/null && compinit -i 2>/dev/null
  fi
  zle -A self-insert _spacue_ins 2>/dev/null
  zle -N self-insert _spacue_self_insert
  zle -A backward-delete-char _spacue_bdel 2>/dev/null
  zle -N backward-delete-char _spacue_backward_delete_char
  zle -A accept-line _spacue_accept 2>/dev/null
  zle -N accept-line _spacue_accept_line
  zle -A send-break _spacue_sbreak 2>/dev/null
  zle -N send-break _spacue_send_break
  zle -A list-expand _spacue_lexpand 2>/dev/null
  zle -N list-expand _spacue_list_expand
  zle -A vi-cmd-mode _spacue_vicmd 2>/dev/null
  zle -N vi-cmd-mode _spacue_vi_cmd_mode
  zle -C spacue-dismiss list-choices _spacue_dismiss_rc 2>/dev/null
  zle -N spacue-esc _spacue_esc
  zle -N spacue-accept _spacue_accept_line
  zle -N spacue-fire _spacue_fire
  bindkey -M emacs "$_spacue_firekey" spacue-fire 2>/dev/null
  bindkey -M viins "$_spacue_firekey" spacue-fire 2>/dev/null
  autoload -Uz add-zsh-hook 2>/dev/null && add-zsh-hook precmd _spacue_precmd 2>/dev/null
}

_spacue_uninstall() {
  autoload -Uz add-zsh-hook 2>/dev/null
  add-zsh-hook -d precmd _spacue_precmd 2>/dev/null
  [[ -n ${widgets[_spacue_ins]} ]] && zle -A _spacue_ins self-insert
  [[ -n ${widgets[_spacue_bdel]} ]] && zle -A _spacue_bdel backward-delete-char
  [[ -n ${widgets[_spacue_accept]} ]] && zle -A _spacue_accept accept-line
  [[ -n ${widgets[_spacue_sbreak]} ]] && zle -A _spacue_sbreak send-break
  [[ -n ${widgets[_spacue_lexpand]} ]] && zle -A _spacue_lexpand list-expand
  [[ -n ${widgets[_spacue_vicmd]} ]] && zle -A _spacue_vicmd vi-cmd-mode
  _spacue_shields_off
  _spacue_beep_restore
  zle -D spacue-dismiss 2>/dev/null
  zle -D spacue-esc 2>/dev/null
  zle -D spacue-accept 2>/dev/null
  bindkey -M emacs -r "$_spacue_firekey" 2>/dev/null
  bindkey -M viins -r "$_spacue_firekey" 2>/dev/null
  zle -D spacue-fire 2>/dev/null
  _spacue_style_off
  _spacue_cleanup_state
  unset _SPACUE_LOADED
}

# public API ----------------------------------------------------------------
spacue_add() {  # VALUE [DESC] [MATCH]  -- append one candidate (for providers)
  _spacue_add "$@"
}
spacue_register() {  # CMD FUNCTION  -- provider fn receives (cmd token args...)
  _spacue_providers[$1]=$2
}
spacue_uninstall() { _spacue_uninstall }

_spacue_install
