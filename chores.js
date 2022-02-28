var START_WEEK = new Date(2021, 3, 11);

function assign_chores(offset, chores, people) {
	var assignments = {};
	for (var i = 0; i < chores.length; i += 1) {
		var person = people[(i + offset) % people.length];
		assignments[chores[i]] = person;
	}
	
	return assignments;
}

function date_to_offset(date) {
	var weekday = date.getDay();
	if (weekday) {
		date.setDate(date.getDate() + 7 - weekday);
	}

	var diff_days = (date - START_WEEK) / (1000 * 60 * 60 * 24);
	if (diff_days > 0) {
		return Math.floor(diff_days / 7);
	}

	return 0;
}

function current_offset() {
	return date_to_offset(new Date());
}

function end_of_week(offset) {
	var date = new Date(START_WEEK.getTime());
	date.setDate(date.getDate() + 7 * offset);
	return date;
}
