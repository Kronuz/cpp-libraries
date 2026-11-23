// A class template shaped like strata's basic_index, for split_check --members and outline.py.
#pragma once

#include <cstddef>
#include <string>
#include <utility>
#include <vector>

namespace demo {

template <class Layout>
class store {
public:
	using size_type = std::size_t;
	struct entry {
		int key = 0;
		int value = 0;
		bool operator==(const entry& o) const noexcept { return key == o.key; }
	};

	explicit store(int capacity, int fill = 0) : capacity_(capacity), items_(static_cast<size_type>(fill)) {
		reserve(capacity);
	}

	~store() {
		items_.clear();
	}

	store& operator=(const store& o) {
		if (this != &o) {
			capacity_ = o.capacity_;
			items_ = o.items_;
		}
		return *this;
	}

	// The number of items: a member type as the return type.
	size_type size() const noexcept {
		return items_.size();
	}

	int get(int key) const& {
		for (const entry& e : items_) {
			if (e.key == key) { return e.value; }
		}
		return -1;
	}

	int get(int key, int fallback) const {
		const int v = get(key);
		return v < 0 ? fallback : v;
	}

	static entry make(int key, int value = 1) {
		entry e;
		e.key = key;
		e.value = value;
		return e;
	}

	template <class F, class G = int>
	void each(F&& f) const {
		for (const entry& e : items_) {
#if defined(DEMO_TRACE)
			trace(e.key);
#endif
			f(e);
		}
	}

	int operator()(int key) const { return get(key); }

	void reserve(int n)
		requires(sizeof(Layout) > 0)
	{
		items_.reserve(static_cast<size_type>(n));
	}

	std::pair<size_type, int> stats() const {
		return {items_.size(), capacity_};
	}

	std::string describe() const {
		return R"(store
	of items)";
	}

private:
	int capacity_;
	std::vector<entry> items_;
};

}  // namespace demo
