const startWeek = new Date(2021, 3, 11); // Sunday 11 APRIL 2021 (note month is 0-indexed)

function assignChores(offset, chores, people) {
	let assignments = {};
	chores.forEach((chore, i) => {
		const person = people[(i + offset) % people.length];
		assignments[chore] = person;
	});

	return assignments;
}

function dateToOffset(date) {
	const weekday = date.getDay();
	if (weekday) {
		date.setDate(date.getDate() + 7 - weekday);
	}

	const diffDays = (date - startWeek) / (1000 * 60 * 60 * 24);
	if (diffDays > 0) {
		return Math.floor(diffDays / 7);
	}

	return 0;
}

function currentOffset() {
	return dateToOffset(new Date());
}

function endOfWeek(offset) {
	const date = new Date(startWeek.getTime());
	date.setDate(date.getDate() + 7 * offset);
	return date;
}
