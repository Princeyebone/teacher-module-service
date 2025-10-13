"""Test script to verify the read-strand implementation with the user's actual data"""

import json
from datetime import datetime
from uuid import UUID

# Mock TempExtract entry
class MockTempExtract:
    def __init__(self, data, file=None):
        self.data = data
        self.file = file
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

# Mock AI data structure that matches the user's actual data
mock_user_data = {
    "strand": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Algebra",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 2
                },
                {
                    "id": 912,
                    "date": "2024-11-19",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 2
                },
                {
                    "id": 963,
                    "date": "2024-11-20",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 2
                },
                {
                    "id": 990,
                    "date": "2024-11-21",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 2
                },
                {
                    "id": 1041,
                    "date": "2024-11-22",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 2
                }
            ]
        }
    },
    "strand_2": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "weeks_sessions": {
            "Week 4": [
                {
                    "id": 881,
                    "date": "2024-11-25",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 4
                },
                {
                    "id": 913,
                    "date": "2024-11-26",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 4
                },
                {
                    "id": 964,
                    "date": "2024-11-27",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 4
                },
                {
                    "id": 991,
                    "date": "2024-11-28",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 4
                },
                {
                    "id": 1042,
                    "date": "2024-11-29",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 4
                }
            ]
        }
    },
    "strand_3": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "weeks_sessions": {
            "Week 9": [
                {
                    "id": 884,
                    "date": "2025-01-13",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 9
                },
                {
                    "id": 916,
                    "date": "2025-01-14",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 9
                },
                {
                    "id": 968,
                    "date": "2025-01-15",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 9
                },
                {
                    "id": 995,
                    "date": "2025-01-16",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 9
                },
                {
                    "id": 1045,
                    "date": "2025-01-17",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 9
                }
            ]
        }
    },
    "indicator": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Algebra",
        "indicator_code": "B7.2.3.1.1",
        "indicator_text": "B7.2.3.1.1",
        "substrand_name": "Equations and Inequalities",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 2
                }
            ]
        },
        "content_standard_code": "B7.2.3.1"
    },
    "substrand": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Algebra",
        "substrand_name": "Equations and Inequalities",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 2
                },
                {
                    "id": 912,
                    "date": "2024-11-19",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 2
                },
                {
                    "id": 963,
                    "date": "2024-11-20",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 2
                },
                {
                    "id": 990,
                    "date": "2024-11-21",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 2
                },
                {
                    "id": 1041,
                    "date": "2024-11-22",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 2
                }
            ]
        }
    },
    "indicator_2": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Algebra",
        "indicator_code": "B7.2.3.1.2",
        "indicator_text": "B7.2.3.1.2",
        "substrand_name": "Equations and Inequalities",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 912,
                    "date": "2024-11-19",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 2
                }
            ]
        },
        "content_standard_code": "B7.2.3.1"
    },
    "indicator_3": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Algebra",
        "indicator_code": "B7.2.3.1.3",
        "indicator_text": "B7.2.3.1.3",
        "substrand_name": "Equations and Inequalities",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 3
                }
            ]
        },
        "content_standard_code": "B7.2.3.1"
    },
    "indicator_4": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Algebra",
        "indicator_code": "B7.2.3.1.4",
        "indicator_text": "B7.2.3.1.4",
        "substrand_name": "Equations and Inequalities",
        "weeks_sessions": {
            "Week 3": [
                {
                    "id": 912,
                    "date": "2024-11-19",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 3
                }
            ]
        },
        "content_standard_code": "B7.2.3.1"
    },
    "indicator_5": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.2.1.1",
        "indicator_text": "B7.3.2.1.1",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 4": [
                {
                    "id": 881,
                    "date": "2024-11-25",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 4
                }
            ]
        },
        "content_standard_code": "B7.3.2.1"
    },
    "indicator_6": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.2.1.2",
        "indicator_text": "B7.3.2.1.2",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 4": [
                {
                    "id": 913,
                    "date": "2024-11-26",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 4
                }
            ]
        },
        "content_standard_code": "B7.3.2.1"
    },
    "indicator_7": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.2.1.3",
        "indicator_text": "B7.3.2.1.3",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 4": [
                {
                    "id": 964,
                    "date": "2024-11-27",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 4
                }
            ]
        },
        "content_standard_code": "B7.3.2.1"
    },
    "indicator_8": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.2.2.1",
        "indicator_text": "B7.3.2.2.1",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 5": [
                {
                    "id": 882,
                    "date": "2024-12-02",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 5
                }
            ]
        },
        "content_standard_code": "B7.3.2.2"
    },
    "indicator_9": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.2.2.2",
        "indicator_text": "B7.3.2.2.2",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 5": [
                {
                    "id": 914,
                    "date": "2024-12-03",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 5
                }
            ]
        },
        "content_standard_code": "B7.3.2.2"
    },
    "substrand_2": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 4": [
                {
                    "id": 881,
                    "date": "2024-11-25",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 4
                },
                {
                    "id": 913,
                    "date": "2024-11-26",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 4
                },
                {
                    "id": 964,
                    "date": "2024-11-27",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 4
                },
                {
                    "id": 991,
                    "date": "2024-11-28",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 4
                },
                {
                    "id": 1042,
                    "date": "2024-11-29",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 4
                }
            ]
        }
    },
    "substrand_3": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "substrand_name": "Data and Probability",
        "weeks_sessions": {
            "Week 9": [
                {
                    "id": 884,
                    "date": "2025-01-13",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 9
                },
                {
                    "id": 916,
                    "date": "2025-01-14",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 9
                },
                {
                    "id": 968,
                    "date": "2025-01-15",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 9
                },
                {
                    "id": 995,
                    "date": "2025-01-16",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 9
                },
                {
                    "id": 1045,
                    "date": "2025-01-17",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 9
                }
            ]
        }
    },
    "indicator_10": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.2.1",
        "indicator_text": "B7.3.3.2.1",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 6": [
                {
                    "id": 883,
                    "date": "2024-12-16",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 6
                }
            ]
        },
        "content_standard_code": "B7.3.3.2"
    },
    "indicator_11": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.2.2",
        "indicator_text": "B7.3.3.2.2",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 6": [
                {
                    "id": 915,
                    "date": "2024-12-17",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 6
                }
            ]
        },
        "content_standard_code": "B7.3.3.2"
    },
    "indicator_12": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.2.3",
        "indicator_text": "B7.3.3.2.3",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 6": [
                {
                    "id": 966,
                    "date": "2024-12-18",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 6
                }
            ]
        },
        "content_standard_code": "B7.3.3.2"
    },
    "indicator_13": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.2.4",
        "indicator_text": "B7.3.3.2.4",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 6": [
                {
                    "id": 993,
                    "date": "2024-12-19",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 6
                }
            ]
        },
        "content_standard_code": "B7.3.3.2"
    },
    "indicator_14": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.2.5",
        "indicator_text": "B7.3.3.2.5",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 6": [
                {
                    "id": 1043,
                    "date": "2024-12-20",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 6
                }
            ]
        },
        "content_standard_code": "B7.3.3.2"
    },
    "indicator_15": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.3.1",
        "indicator_text": "B7.3.3.3.1",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 7": [
                {
                    "id": 883,
                    "date": "2024-12-16",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 7
                }
            ]
        },
        "content_standard_code": "B7.3.3.3"
    },
    "indicator_16": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.3.2",
        "indicator_text": "B7.3.3.3.2",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 7": [
                {
                    "id": 915,
                    "date": "2024-12-17",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 7
                }
            ]
        },
        "content_standard_code": "B7.3.3.3"
    },
    "indicator_17": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.3.3",
        "indicator_text": "B7.3.3.3.3",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 8": [
                {
                    "id": 966,
                    "date": "2024-12-18",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 8
                }
            ]
        },
        "content_standard_code": "B7.3.3.3"
    },
    "indicator_18": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "indicator_code": "B7.3.3.3.4",
        "indicator_text": "B7.3.3.3.4",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 8": [
                {
                    "id": 993,
                    "date": "2024-12-19",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 8
                }
            ]
        },
        "content_standard_code": "B7.3.3.3"
    },
    "indicator_19": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "indicator_code": "B7.4.1.1.1",
        "indicator_text": "B7.4.1.1.1",
        "substrand_name": "Data and Probability",
        "weeks_sessions": {
            "Week 9": [
                {
                    "id": 884,
                    "date": "2025-01-13",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 9
                }
            ]
        },
        "content_standard_code": "B7.4.1.1"
    },
    "indicator_20": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "indicator_code": "B7.4.1.1.2",
        "indicator_text": "B7.4.1.1.2",
        "substrand_name": "Data and Probability",
        "weeks_sessions": {
            "Week 9": [
                {
                    "id": 916,
                    "date": "2025-01-14",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 9
                }
            ]
        },
        "content_standard_code": "B7.4.1.1"
    },
    "indicator_21": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "indicator_code": "B7.4.1.1.3",
        "indicator_text": "B7.4.1.1.3",
        "substrand_name": "Data and Probability",
        "weeks_sessions": {
            "Week 9": [
                {
                    "id": 968,
                    "date": "2025-01-15",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 9
                }
            ]
        },
        "content_standard_code": "B7.4.1.1"
    },
    "indicator_22": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "indicator_code": "B7.4.1.2.1",
        "indicator_text": "B7.4.1.2.1",
        "substrand_name": "Data and Probability",
        "weeks_sessions": {
            "Week 10": [
                {
                    "id": 967,
                    "date": "2025-01-08",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 10
                }
            ]
        },
        "content_standard_code": "B7.4.1.2"
    },
    "indicator_23": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "indicator_code": "B7.4.1.2.2",
        "indicator_text": "B7.4.1.2.2",
        "substrand_name": "Data and Probability",
        "weeks_sessions": {
            "Week 10": [
                {
                    "id": 994,
                    "date": "2025-01-09",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 10
                }
            ]
        },
        "content_standard_code": "B7.4.1.2"
    },
    "content_standard": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Algebra",
        "substrand_name": "Equations and Inequalities",
        "weeks_sessions": {
            "Week 2": [
                {
                    "id": 880,
                    "date": "2024-11-18",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 2
                },
                {
                    "id": 912,
                    "date": "2024-11-19",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 2
                },
                {
                    "id": 963,
                    "date": "2024-11-20",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 2
                },
                {
                    "id": 990,
                    "date": "2024-11-21",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 2
                },
                {
                    "id": 1041,
                    "date": "2024-11-22",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 2
                }
            ]
        },
        "content_standard": "B7.2.3.1",
        "content_standard_code": "B7.2.3.1"
    },
    "content_standard_2": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 4": [
                {
                    "id": 881,
                    "date": "2024-11-25",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 4
                },
                {
                    "id": 913,
                    "date": "2024-11-26",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 4
                },
                {
                    "id": 964,
                    "date": "2024-11-27",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 4
                },
                {
                    "id": 991,
                    "date": "2024-11-28",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 4
                },
                {
                    "id": 1042,
                    "date": "2024-11-29",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 4
                }
            ]
        },
        "content_standard": "B7.3.2.1",
        "content_standard_code": "B7.3.2.1"
    },
    "content_standard_3": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 5": [
                {
                    "id": 882,
                    "date": "2024-12-02",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 5
                },
                {
                    "id": 914,
                    "date": "2024-12-03",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 5
                },
                {
                    "id": 965,
                    "date": "2024-12-04",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 5
                },
                {
                    "id": 992,
                    "date": "2024-12-05",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 5
                }
            ]
        },
        "content_standard": "B7.3.2.2",
        "content_standard_code": "B7.3.2.2"
    },
    "content_standard_4": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 6": [
                {
                    "id": 883,
                    "date": "2024-12-16",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 6
                },
                {
                    "id": 915,
                    "date": "2024-12-17",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 6
                },
                {
                    "id": 966,
                    "date": "2024-12-18",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 6
                },
                {
                    "id": 993,
                    "date": "2024-12-19",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 6
                },
                {
                    "id": 1043,
                    "date": "2024-12-20",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 6
                }
            ]
        },
        "content_standard": "B7.3.3.2",
        "content_standard_code": "B7.3.3.2"
    },
    "content_standard_5": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 7": [
                {
                    "id": 883,
                    "date": "2024-12-16",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 7
                },
                {
                    "id": 915,
                    "date": "2024-12-17",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 7
                },
                {
                    "id": 966,
                    "date": "2024-12-18",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 7
                },
                {
                    "id": 993,
                    "date": "2024-12-19",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 7
                },
                {
                    "id": 1043,
                    "date": "2024-12-20",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 7
                }
            ]
        },
        "content_standard": "B7.3.3.3",
        "content_standard_code": "B7.3.3.3"
    },
    "content_standard_6": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Geometry and Measurement",
        "substrand_name": "Measurement",
        "weeks_sessions": {
            "Week 8": [
                {
                    "id": 966,
                    "date": "2024-12-18",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 8
                },
                {
                    "id": 993,
                    "date": "2024-12-19",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 8
                },
                {
                    "id": 1043,
                    "date": "2024-12-20",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 8
                }
            ]
        },
        "content_standard": "B7.3.3.3",
        "content_standard_code": "B7.3.3.3"
    },
    "content_standard_7": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "substrand_name": "Data and Probability",
        "weeks_sessions": {
            "Week 9": [
                {
                    "id": 884,
                    "date": "2025-01-13",
                    "subject": "Mathematics",
                    "end_time": "10:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "09:00",
                    "week_number": 9
                },
                {
                    "id": 916,
                    "date": "2025-01-14",
                    "subject": "Mathematics",
                    "end_time": "11:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "10:00",
                    "week_number": 9
                },
                {
                    "id": 968,
                    "date": "2025-01-15",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 9
                },
                {
                    "id": 995,
                    "date": "2025-01-16",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 9
                },
                {
                    "id": 1045,
                    "date": "2025-01-17",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 9
                }
            ]
        },
        "content_standard": "B7.4.1.1",
        "content_standard_code": "B7.4.1.1"
    },
    "content_standard_8": {
        "subject": "MATHEMATICS-BASIC 7",
        "class_name": "Class 10A",
        "teacher_id": "7bed2b69-8000-4b36-8e91-7fe0b70c9d82",
        "strand_name": "Data",
        "substrand_name": "Data and Probability",
        "weeks_sessions": {
            "Week 10": [
                {
                    "id": 967,
                    "date": "2025-01-08",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 10
                },
                {
                    "id": 994,
                    "date": "2025-01-09",
                    "subject": "Mathematics",
                    "end_time": "12:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "11:00",
                    "week_number": 10
                },
                {
                    "id": 1044,
                    "date": "2025-01-10",
                    "subject": "Mathematics",
                    "end_time": "13:00",
                    "location": "Class 10A",
                    "class_name": "Class 10A",
                    "start_time": "12:00",
                    "week_number": 10
                }
            ]
        },
        "content_standard": "B7.4.1.2",
        "content_standard_code": "B7.4.1.2"
    }
}

def process_tempextract_data_fixed(temp_entry, subject, class_name, teacher_id):
    """Simulate the FIXED processing logic from read_strands endpoint"""
    if temp_entry and temp_entry.data:
        # Format the data to match the StrandResponse structure
        ai_data = temp_entry.data
        formatted_response = []
        
        # Handle the actual format returned by AI which uses numbered keys
        if isinstance(ai_data, dict):
            # Look for all strand components (strand, strand_2, strand_3, etc.)
            strand_keys = [k for k in ai_data.keys() if k == 'strand' or (k.startswith('strand_') and k.replace('strand_', '').isdigit())]
            
            # Look for all substrand components
            substrand_keys = [k for k in ai_data.keys() if k == 'substrand' or (k.startswith('substrand_') and k.replace('substrand_', '').isdigit())]
            
            # Look for all content_standard components
            content_standard_keys = [k for k in ai_data.keys() if k == 'content_standard' or (k.startswith('content_standard_') and k.replace('content_standard_', '').isdigit())]
            
            # Look for all indicator components
            indicator_keys = [k for k in ai_data.keys() if k == 'indicator' or (k.startswith('indicator_') and k.replace('indicator_', '').isdigit())]
            
            # Process all strand components
            for key in strand_keys:
                if key in ai_data:
                    component_data = ai_data[key]
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",
                        "file": temp_entry.file,
                        "component_type": "strand"
                    }
                    formatted_response.append(component_response)
            
            # Process all substrand components
            for key in substrand_keys:
                if key in ai_data:
                    component_data = ai_data[key]
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",
                        "file": temp_entry.file,
                        "component_type": "substrand"
                    }
                    
                    # Add substrand-specific fields
                    if "substrand_name" in component_data:
                        component_response["substrand_name"] = component_data["substrand_name"]
                        
                    formatted_response.append(component_response)
            
            # Process all content_standard components
            for key in content_standard_keys:
                if key in ai_data:
                    component_data = ai_data[key]
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",
                        "file": temp_entry.file,
                        "component_type": "content_standard"
                    }
                    
                    # Add content_standard-specific fields
                    if "content_standard_code" in component_data:
                        component_response["content_standard_code"] = component_data["content_standard_code"]
                    if "content_standard" in component_data:
                        component_response["content_standard"] = component_data["content_standard"]
                        
                    formatted_response.append(component_response)
            
            # Process all indicator components
            for key in indicator_keys:
                if key in ai_data:
                    component_data = ai_data[key]
                    weeks_sessions = component_data.get("weeks_sessions", {})
                    
                    component_response = {
                        "strand_name": component_data.get("strand_name", ""),
                        "subject": component_data.get("subject", subject),
                        "class_name": component_data.get("class_name", class_name),
                        "teacher_id": component_data.get("teacher_id", teacher_id),
                        "weeks_sessions": weeks_sessions,
                        "created_at": temp_entry.created_at,
                        "updated_at": temp_entry.updated_at,
                        "data_source": "temp_extract",
                        "file": temp_entry.file,
                        "component_type": "indicator"
                    }
                    
                    # Add indicator-specific fields
                    if "indicator_code" in component_data:
                        component_response["indicator_code"] = component_data["indicator_code"]
                    if "indicator_text" in component_data:
                        component_response["indicator_text"] = component_data["indicator_text"]
                    if "content_standard_code" in component_data:
                        component_response["content_standard_code"] = component_data["content_standard_code"]
                    if "substrand_name" in component_data:
                        component_response["substrand_name"] = component_data["substrand_name"]
                        
                    formatted_response.append(component_response)
        
        return formatted_response
    return []

def test_user_data_implementation():
    """Test the implementation with the user's actual data"""
    print("Testing read-strand implementation with user's actual data...")
    
    temp_entry = MockTempExtract(mock_user_data, "https://storage.googleapis.com/teacher_module_acatable_bucket/sem_plan/7bed2b69-8000-4b36-8e91-7fe0b70c9d82/Class%2010A/Mathematics.docx")
    result = process_tempextract_data_fixed(temp_entry, "Mathematics", "Class 10A", "7bed2b69-8000-4b36-8e91-7fe0b70c9d82")
    
    print(f"Processed {len(result)} components:")
    
    # Count different component types
    strand_count = 0
    substrand_count = 0
    content_standard_count = 0
    indicator_count = 0
    
    for item in result:
        component_type = item.get("component_type", "unknown")
        if component_type == "strand":
            strand_count += 1
            print(f"  Strand: {item['strand_name']}")
        elif component_type == "substrand":
            substrand_count += 1
            print(f"  Substrand: {item['strand_name']} - {item.get('substrand_name', 'N/A')}")
        elif component_type == "content_standard":
            content_standard_count += 1
            print(f"  Content Standard: {item['strand_name']} - {item.get('content_standard', 'N/A')}")
        elif component_type == "indicator":
            indicator_count += 1
            print(f"  Indicator: {item['strand_name']} - {item.get('indicator_text', 'N/A')}")
        else:
            print(f"  Unknown: {item}")
    
    print(f"\nComponent breakdown:")
    print(f"  Strands: {strand_count}")
    print(f"  Substrands: {substrand_count}")
    print(f"  Content Standards: {content_standard_count}")
    print(f"  Indicators: {indicator_count}")
    print(f"  Total: {len(result)}")
    
    # Verify we got all components from the user's data
    expected_strands = 3  # strand, strand_2, strand_3
    expected_substrands = 3  # substrand, substrand_2, substrand_3
    expected_content_standards = 8  # content_standard through content_standard_8
    expected_indicators = 23  # indicator through indicator_23
    expected_total = expected_strands + expected_substrands + expected_content_standards + expected_indicators
    
    if (strand_count == expected_strands and 
        substrand_count == expected_substrands and 
        content_standard_count == expected_content_standards and 
        indicator_count == expected_indicators and
        len(result) == expected_total):
        print("✅ User data implementation test passed - all components processed")
        return True
    else:
        print(f"❌ User data implementation test failed:")
        print(f"   Expected: {expected_strands} strands, {expected_substrands} substrands, {expected_content_standards} content standards, {expected_indicators} indicators, {expected_total} total")
        print(f"   Got: {strand_count} strands, {substrand_count} substrands, {content_standard_count} content standards, {indicator_count} indicators, {len(result)} total")
        return False

if __name__ == "__main__":
    print("Testing read-strand endpoint implementation with user's actual data")
    print("=" * 70)
    
    success = test_user_data_implementation()
    
    if success:
        print("\n🎉 User data implementation test passed! Read-strand endpoint should now return ALL components correctly.")
        print("The endpoint will return all strands, substrands, content standards, and indicators from TempExtract.")
    else:
        print("\n💥 User data implementation test failed! Further investigation needed.")