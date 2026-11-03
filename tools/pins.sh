#!/usr/bin/env bash
# Lists the first-party FetchContent pins of the Kronuz repositories and whether each pin is
# behind the head of its dependency's default branch.
#
#   tools/pins.sh [-r DIR] [-o OWNER] [-j N] [-b] [-c] [REPO...]
#
# A pin is a FetchContent_Declare in a CMakeLists.txt or *.cmake file of the consumer's default
# branch whose GIT_REPOSITORY is github.com/OWNER/<dependency>. One row per pin:
#
#   consumer  file  dependency  pin  default-branch  status
#
# The status is `current` (the pin is the head), `current (+N ci/docs)` (the head is N commits past
# the pin, and they change only .github/**, docs/** and top-level *.md, which cannot affect a
# consumer's build), `behind N` (the head is N commits past the pin, some of them changing more),
# `tracks BRANCH` (GIT_TAG names a branch, so the build follows its tip), `ahead N (not on
# BRANCH)`, `diverged (+A on BRANCH, +B on the pin)`, `pin not found`, `unresolved: ${VAR}` (a
# variable the file does not set), or `no GIT_TAG`. A `set(NAME value)` in the same file resolves
# ${NAME}.
#
#   REPO...    the consumers to read (default: every repository of OWNER that is not archived).
#   -r DIR     read local clones DIR/<name> (their origin/HEAD, or HEAD without a remote) instead
#              of GitHub; `git fetch` them first for current heads.
#   -o OWNER   the GitHub owner (default Kronuz, or $PINS_OWNER).
#   -j N       consumers read at once (default 8).
#   -b         print only the pins that need attention: behind, ahead, diverged, not found,
#              unresolved or without a GIT_TAG.
#   -c         exit 1 when any pin needs attention (implies -b).
#
# GitHub mode needs `gh`, signed in. Both modes need perl.
# `pins.sh --parse LABEL < FILE` prints the first-party declares of one CMake file as
# LABEL, name, dependency and GIT_TAG, tab separated.
set -uo pipefail

OWNER="${PINS_OWNER:-Kronuz}"

# stdin: CMake text; $1: the file's label. Prints label, declare name, dependency, GIT_TAG.
parse_cmake() {
	OWNER="$OWNER" perl -e '
		my $file = shift @ARGV;
		my $owner = $ENV{OWNER};
		my $text = do { local $/; <STDIN> };
		$text =~ s/#[^\n]*//g;
		my %var;
		while ($text =~ /\bset\s*\(\s*(\w+)\s+"?([^\s")]+)"?/gi) { $var{$1} //= $2; }
		sub expand { my $s = shift; $s =~ s/\$\{(\w+)\}/exists $var{$1} ? $var{$1} : "\${$1}"/ge; return $s; }
		while ($text =~ /\bFetchContent_Declare\s*\(\s*([^\s()]+)([^)]*)\)/gi) {
			my ($name, $body) = ($1, $2);
			my ($url) = $body =~ /\bGIT_REPOSITORY\s+"?([^\s")]+)/;
			next unless defined $url;
			my ($tag) = $body =~ /\bGIT_TAG\s+"?([^\s")]+)/;
			$url = expand($url);
			next unless $url =~ m{github\.com[/:]\Q$owner\E/([A-Za-z0-9._-]+?)(?:\.git)?/?$}i;
			my $dep = $1;
			print join("\t", $file, $name, $dep, defined $tag ? expand($tag) : ""), "\n";
		}
	' "$1"
}

cmake_filter() { grep -E '(^|/)CMakeLists\.txt$|\.cmake$' | grep -v -E '(^|/)(third_party|_deps|vendor|build[^/]*)/'; }

# -- GitHub ------------------------------------------------------------------------------------
api_files() { gh api "repos/$OWNER/$1/git/trees/$2?recursive=1" --jq '.tree[] | select(.type == "blob") | .path' 2>/dev/null | cmake_filter; }
api_read() { gh api -H "Accept: application/vnd.github.raw" "repos/$OWNER/$1/contents/$3?ref=$2" 2>/dev/null; }
# "A B": A commits the head has past the pin, B commits the pin has past the head.
api_compare() { gh api "repos/$OWNER/$1/compare/$3...$2" --jq '"\(.ahead_by) \(.behind_by)"' 2>/dev/null; }
# The files the commits from pin $3 to head $2 change; fails when the range cannot be read.
api_changed() { gh api --paginate "repos/$OWNER/$1/compare/$3...$2" --jq '.files[].filename'; }
api_branch() { awk -F'\t' -v d="$1" '$1 == d { print $2; exit }' "$PINS_OUT/.branches"; }

# -- local clones ------------------------------------------------------------------------------
local_ref() { if git -C "$1" rev-parse --verify -q origin/HEAD >/dev/null 2>&1; then echo origin/HEAD; else echo HEAD; fi; }
local_files() { git -C "$PINS_ROOT/$1" ls-tree -r --name-only "$(local_ref "$PINS_ROOT/$1")" 2>/dev/null | cmake_filter; }
local_read() { git -C "$PINS_ROOT/$1" show "$(local_ref "$PINS_ROOT/$1"):$3" 2>/dev/null; }
local_compare() {
	local dir="$PINS_ROOT/$1" counts
	[ -d "$dir/.git" ] || [ -f "$dir/.git" ] || return 1
	counts="$(git -C "$dir" rev-list --left-right --count "$3...$(local_ref "$dir")" 2>/dev/null)" || return 1
	# shellcheck disable=SC2086
	set -- $counts
	echo "$2 $1"
}
local_changed() { git -C "$PINS_ROOT/$1" diff --name-only "$3" "$(local_ref "$PINS_ROOT/$1")"; }
local_branch() {
	local dir="$PINS_ROOT/$1" name
	name="$(git -C "$dir" symbolic-ref --short -q refs/remotes/origin/HEAD 2>/dev/null)" ||
		name="$(git -C "$dir" symbolic-ref --short -q HEAD 2>/dev/null)" || return 1
	echo "${name#origin/}"
}

# -- one consumer ------------------------------------------------------------------------------
backend() { # function suffix
	if [ -n "${PINS_ROOT:-}" ]; then echo "local_$1"; else echo "api_$1"; fi
}

# Succeeds when the commits from pin $3 to head $2 of dependency $1 change only files that cannot
# affect a consumer's build: .github/**, docs/** and top-level *.md.
only_inert() {
	local files
	files="$("$(backend changed)" "$1" "$2" "$3")" || return 1
	! grep -q -v -E '^(\.github/|docs/)|^[^/]+\.md$' <<<"$files"
}

status_of() { # dependency tag
	local dep=$1 tag=$2 branch res a b
	branch="$("$(backend branch)" "$dep")"
	if [ -z "$tag" ]; then echo "no GIT_TAG"; return; fi
	# shellcheck disable=SC2016
	case $tag in *'${'*) echo "unresolved: $tag"; return ;; esac
	if [ -z "$branch" ]; then echo "dependency not found"; return; fi
	if [ "$tag" = "$branch" ] || [ "$tag" = main ] || [ "$tag" = master ]; then echo "tracks $tag"; return; fi
	res="$("$(backend compare)" "$dep" "$branch" "$tag")" || { echo "pin not found"; return; }
	# shellcheck disable=SC2086
	set -- $res
	a=$1 b=$2
	if [ "$a" -eq 0 ] && [ "$b" -eq 0 ]; then echo current
	elif [ "$b" -eq 0 ]; then
		if only_inert "$dep" "$branch" "$tag"; then echo "current (+$a ci/docs)"; else echo "behind $a"; fi
	elif [ "$a" -eq 0 ]; then echo "ahead $b (not on $branch)"
	else echo "diverged (+$a on $branch, +$b on the pin)"; fi
}

scan_repo() { # consumer, its default branch
	local repo=$1 branch=$2 file dep tag name label cached status
	: >"$PINS_OUT/$repo"
	"$(backend files)" "$repo" "$branch" | while IFS= read -r file; do
		"$(backend read)" "$repo" "$branch" "$file" | parse_cmake "$file"
	done | while IFS=$'\t' read -r file name dep tag; do
		label=$tag
		[[ $tag =~ ^[0-9a-f]{40}$ ]] && label="${tag:0:10}"
		cached="$PINS_OUT/.cache/${dep}__${tag//\//_}"
		if [ -f "$cached" ]; then status="$(cat "$cached")"; else
			status="$(status_of "$dep" "$tag")"
			mkdir -p "$PINS_OUT/.cache" && echo "$status" >"$cached"
		fi
		printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$repo" "$file" "$dep" "${label:--}" \
			"$("$(backend branch)" "$dep")" "$status" >>"$PINS_OUT/$repo"
	done
}

needs_attention() { # rows on stdin
	grep -E $'\t(behind|ahead|diverged|pin not found|unresolved|no GIT_TAG|dependency not found)'
}

case "${1:-}" in
--parse) parse_cmake "${2:?usage: pins.sh --parse LABEL < FILE}"; exit ;;
--repo) shift; scan_repo "$1" "$2"; exit ;;
esac

usage() { sed -n '2,/^set -u/p' "$0" | sed '$d' | sed 's/^# \{0,1\}//' >&2; exit 2; }

root="" jobs=8 only=0 check=0
while getopts "r:o:j:bch" opt; do
	case $opt in
	r) root="$(cd "$OPTARG" && pwd)" || exit 2 ;;
	o) OWNER=$OPTARG ;;
	j) jobs=$OPTARG ;;
	b) only=1 ;;
	c) only=1 check=1 ;;
	*) usage ;;
	esac
done
shift $((OPTIND - 1))

PINS_OUT="$(mktemp -d)"
trap 'rm -rf "$PINS_OUT"' EXIT
export OWNER PINS_OUT
if [ -n "$root" ]; then
	PINS_ROOT=$root
	export PINS_ROOT
	for dir in "$root"/*/; do
		name="$(basename "$dir")"
		[ -e "$dir/.git" ] || continue
		printf '%s\t%s\n' "$name" "$(local_branch "$name")"
	done >"$PINS_OUT/.branches"
else
	command -v gh >/dev/null || { echo "pins: gh is not installed" >&2; exit 2; }
	gh repo list "$OWNER" --limit 1000 --no-archived --json name,defaultBranchRef \
		--jq '.[] | select(.defaultBranchRef != null) | "\(.name)\t\(.defaultBranchRef.name)"' \
		>"$PINS_OUT/.branches" || { echo "pins: gh repo list failed" >&2; exit 2; }
fi
sort -o "$PINS_OUT/.branches" "$PINS_OUT/.branches"

if [ $# -gt 0 ]; then
	for repo in "$@"; do awk -F'\t' -v r="$repo" '$1 == r' "$PINS_OUT/.branches"; done
else
	cat "$PINS_OUT/.branches"
fi >"$PINS_OUT/.consumers"
[ -s "$PINS_OUT/.consumers" ] || { echo "pins: no repositories to read" >&2; exit 2; }

tr '\t\n' '\0\0' <"$PINS_OUT/.consumers" | xargs -0 -n 2 -P "$jobs" "$(cd "$(dirname "$0")" && pwd)/$(basename "$0")" --repo

rows="$PINS_OUT/.rows"
: >"$rows"
while IFS=$'\t' read -r repo _; do cat "$PINS_OUT/$repo" 2>/dev/null; done <"$PINS_OUT/.consumers" >"$rows"
shown="$PINS_OUT/.shown"
if [ $only -eq 1 ]; then needs_attention <"$rows" >"$shown" || true; else cp "$rows" "$shown"; fi
if [ -s "$shown" ]; then
	{ printf 'consumer\tfile\tdependency\tpin\tdefault\tstatus\n'; cat "$shown"; } | column -t -s $'\t'
fi
total=$(wc -l <"$rows" | tr -d ' ')
attention=$(needs_attention <"$rows" | wc -l | tr -d ' ')
echo "pins: $total first-party pins in $(wc -l <"$PINS_OUT/.consumers" | tr -d ' ') repositories, $attention need attention"
[ $check -eq 0 ] || [ "$attention" -eq 0 ]
