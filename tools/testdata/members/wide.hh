// A non-template class shaped like uinteger_t, for split_check --members and outline.py.
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <type_traits>

#define WIDE_PRIVATE private
#define WIDE_NOINLINE __attribute__((noinline))

class wide {
public:
	using digit = std::uint64_t;

	class container {
	public:
		using size_type = std::size_t;
		using iterator = digit*;

		container() noexcept : _p(_local), _size(0) { }

		container(const container& o) : _p(_local), _size(o._size) {
			copy(o);
		}

		iterator begin() noexcept { return _p; }

		iterator end() noexcept {
			return _p + _size;
		}

		size_type size() const noexcept { return _size; }

	private:
		void copy(const container& o) {
			for (size_type i = 0; i < o._size; ++i) {
				_local[i] = o._p[i];
			}
		}

		digit _local[4] = {};
		digit* _p;
		size_type _size;
	};

	wide() = default;

	explicit wide(digit v) : _value() {
		set(v);
	}

	static digit low(digit x, unsigned bits = 32) {
		return x & ((digit(1) << bits) - 1);
	}

	WIDE_NOINLINE digit high(digit x) const {
		return x >> 32;
	}

	template <typename T, typename = typename std::enable_if<std::is_integral<T>::value>::type>
	void set(T v) {
		(void)v;
	}

	static digit hi_part(digit x) { return x >> 32; }
	static digit lo_part(digit x) { return x & 0xffffffffu; }

	static digit (*selector(bool hi))(digit) {
		return hi ? &hi_part : &lo_part;
	}

	static void (*pick(unsigned k))(const digit&, unsigned char*) {
		if (k == 0) { return &emit0; }
		return &emit1;
	}

	static void emit0(const digit& d, unsigned char* out) { *out = static_cast<unsigned char>(d); }
	static void emit1(const digit& d, unsigned char* out) { *out = static_cast<unsigned char>(d >> 8); }

#if defined __clang__
#  define WIDE_UNROLL _Pragma("clang loop unroll(full)")
#else
#  define WIDE_UNROLL
#endif

	static int sum(const int* x, int n) {
		int s = 0;
		WIDE_UNROLL
		for (int i = 0; i < n; ++i) {
			s += x[i];
		}
		return s;
	}

#undef WIDE_UNROLL

	container::iterator first() {
		return _value.begin();
	}

	std::string str() const {
		std::string out;
#if defined(WIDE_DEBUG)
		out += "dbg";
#endif
		return out;
	}

WIDE_PRIVATE:
	void set(digit v) {
		*_value.begin() = v;
	}

	container _value;
};

#undef WIDE_PRIVATE
